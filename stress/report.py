"""Show the results: a short summary in the terminal, charts (PNG), a
self-contained HTML report that opens in your browser, and an Excel workbook
with every number, for anyone who wants to check the maths.
"""

import base64
import html
import io
import textwrap
import webbrowser
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # draw charts to files; no pop-up windows
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

from . import explorer  # noqa: E402

# One palette for charts and the HTML page, so they read as one document.
INK, MUTED, RULE = "#17252F", "#5B6B75", "#D3DADF"
LOSS_COLOUR, GAIN_COLOUR = "#B4412F", "#2E7A68"
CLASS_COLOURS = {
    "Equities": "#2F4B63", "Government bonds": "#6E9CB8", "Corporate bonds": "#9DB5A0",
    "Commodities": "#C39A3E", "Real estate": "#8C6D8F", "Cash": "#B8C0C6",
}
SPARE_COLOURS = ["#5E7F6E", "#A5675A", "#7A7FA8", "#B3A36B"]
MINUS = "\u2212"  # a real minus sign reads better than a hyphen in tables


# ================================================================ formatting

def signed(x, dp):
    """'+1.2' or '−1.2', but plain '0.0' when the rounded value is zero."""
    r = round(float(x), dp)
    if r == 0:
        return "%.*f" % (dp, 0.0)
    return ("%+.*f" % (dp, r)).replace("-", MINUS)


def pct(x, dp=1):
    if x is None or pd.isna(x):
        return "n/a"
    return signed(x * 100, dp) + "%"


def money(x):
    if x is None or pd.isna(x):
        return "n/a"
    r = round(float(x))
    if r == 0:
        return "$0"
    return "%s$%s" % (MINUS if r < 0 else "+", format(abs(r), ",.0f"))


def bp(x):
    if x is None or pd.isna(x):
        return "n/a"
    return signed(x, 0) + " bp"


def plain(text):
    """Terminal version: an ordinary hyphen works in every console encoding."""
    return text.replace(MINUS, "-")


def sign_class(x):
    if x is None or pd.isna(x) or abs(x) < 1e-9:
        return ""
    return "neg" if x < 0 else "pos"


def wrap(text, width=18):
    return "\n".join(textwrap.wrap(text, width)) or text


def readable_betas(model, factors):
    """Betas as '% move of the holding' for +1% (returns) or +10 bp (yields)."""
    out = pd.DataFrame(index=model.betas.index)
    for key, spec in factors.items():
        if spec["kind"] == "yield":
            out["%s, per +10 bp (%%)" % spec["label"]] = model.betas[key] * 10 * 100
        else:
            out["%s, per +1%% (%%)" % spec["label"]] = model.betas[key]
    out["R squared"] = model.stats["r2"].astype(float)
    out["Weeks of data"] = model.stats["weeks"].astype(int)
    return out


# ================================================================ terminal

def print_summary(portfolio, hist, scen, model, summary_mode):
    value = portfolio["value"].sum()
    print("=" * 78)
    print("PORTFOLIO STRESS TEST   value $%s   holdings %d" % (format(value, ",.0f"), len(portfolio)))
    print("=" * 78)

    if not hist["summary"].empty:
        print("\nPast crises replayed on today's portfolio")
        print("  %-40s %10s %14s %12s" % ("Regime", "Return", "Gain/loss", "Worst dip"))
        for name, row in hist["summary"].sort_values("portfolio_return").iterrows():
            flag = " *" if row["estimated"] else ""
            print(plain("  %-40s %10s %14s %12s" % (
                (name + flag)[:40], pct(row["portfolio_return"]), money(row["pnl"]),
                pct(row["max_drawdown"]))))
        if hist["summary"]["estimated"].astype(bool).any():
            print("  * includes holdings estimated from the factor model (no prices yet)")

    print("\nHypothetical shocks (isolated = only the named factors move;"
          " correlated = others follow)")
    print("  %-54s %9s %11s %13s" % ("Scenario", "Isolated", "Correlated", "Gain/loss"))
    for name, row in scen["summary"].sort_values(summary_mode + "_return").iterrows():
        print(plain("  %-54s %9s %11s %13s" % (
            name[:54], pct(row["isolated_return"]), pct(row["correlated_return"]),
            money(row[summary_mode + "_pnl"]))))
    print("  (Gain/loss uses the %s version.)" % summary_mode)

    warnings = model.warnings + hist["warnings"] + scen["warnings"]
    if warnings:
        print("\nPlease note:")
        for w in warnings:
            print("  - " + plain(w))
    print()


# ================================================================ charts

def _style():
    plt.rcParams.update({
        "font.family": "sans-serif", "font.size": 9.5,
        "axes.edgecolor": RULE, "axes.labelcolor": INK, "axes.titlecolor": INK,
        "axes.titlesize": 10.5, "axes.titleweight": "bold",
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": MUTED, "ytick.color": MUTED, "legend.frameon": False,
        "figure.facecolor": "white", "savefig.dpi": 150,
    })


def _class_colour(name, i):
    return CLASS_COLOURS.get(name, SPARE_COLOURS[i % len(SPARE_COLOURS)])


def chart_heatmap(returns, estimated, title):
    """Holdings down the side, regimes across the top, return in each cell."""
    data = returns * 100
    limit = max(1.0, float(np.nanmax(np.abs(data.to_numpy()))))
    cmap = LinearSegmentedColormap.from_list("lossgain", [LOSS_COLOUR, "#FFFFFF", GAIN_COLOUR])
    fig, ax = plt.subplots(figsize=(1.25 * data.shape[1] + 2.2, 0.42 * data.shape[0] + 1.9))
    ax.imshow(data.to_numpy(), cmap=cmap, aspect="auto",
              norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit))
    for i, ticker in enumerate(data.index):
        for j, regime in enumerate(data.columns):
            v = data.iloc[i, j]
            if pd.isna(v):
                continue
            mark = "*" if ticker in estimated.get(regime, []) else ""
            colour = "white" if abs(v) > 0.6 * limit else INK
            ax.text(j, i, signed(v, 0).lstrip("+") + mark,
                    ha="center", va="center", fontsize=8.5, color=colour)
    ax.set_xticks(range(data.shape[1]), [wrap(c, 14) for c in data.columns], fontsize=8)
    ax.set_yticks(range(data.shape[0]), data.index)
    ax.tick_params(length=0)
    ax.xaxis.tick_top()
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(title, loc="left", pad=10)
    fig.tight_layout()
    return fig


def chart_paths(paths):
    """One small chart per regime: portfolio value from the first day."""
    n = len(paths)
    cols = min(4, n)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(3.0 * cols, 2.35 * rows),
                             sharey=True, squeeze=False)
    for ax, (name, path) in zip(axes.flat, paths.items()):
        y = (path.to_numpy() - 1) * 100
        x = np.arange(len(y))
        ax.plot(x, y, color=INK, linewidth=1.4)
        ax.fill_between(x, y, 0, where=y < 0, interpolate=True, color=LOSS_COLOUR,
                        alpha=0.18, linewidth=0)
        ax.fill_between(x, y, 0, where=y >= 0, interpolate=True, color=GAIN_COLOUR,
                        alpha=0.18, linewidth=0)
        ax.axhline(0, color=RULE, linewidth=0.8)
        ax.set_title(wrap(name, 30), loc="left", fontsize=9)
        ax.annotate(signed(y[-1], 1) + "%", (x[-1], y[-1]),
                    textcoords="offset points", xytext=(-2, 6), ha="right",
                    fontsize=8.5, color=LOSS_COLOUR if y[-1] < 0 else GAIN_COLOUR,
                    bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.85})
        ax.set_xlabel("trading days", fontsize=8, color=MUTED)
    for ax in axes.flat[n:]:
        ax.axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("portfolio change (%)", fontsize=8)
    fig.tight_layout()
    return fig


def chart_contributions(contributions, totals, title):
    """Which asset classes caused each gain or loss (bars) and the total (diamond)."""
    data = contributions.loc[totals.sort_values().index] * 100
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(9.5, 0.5 * len(data) + 1.7))
    left_pos, left_neg = np.zeros(len(data)), np.zeros(len(data))
    for i, cls in enumerate(data.columns):
        values = data[cls].to_numpy()
        pos, neg = np.where(values > 0, values, 0), np.where(values < 0, values, 0)
        colour = _class_colour(cls, i)
        ax.barh(y, pos, left=left_pos, color=colour, height=0.62, label=cls)
        ax.barh(y, neg, left=left_neg, color=colour, height=0.62)
        left_pos += pos
        left_neg += neg
    ax.scatter(totals.loc[data.index] * 100, y, marker="D", s=30, color=INK, zorder=3,
               label="Total")
    ax.axvline(0, color=MUTED, linewidth=0.8)
    ax.set_yticks(y, [wrap(n, 38) for n in data.index], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("contribution to portfolio return (percentage points)")
    ax.set_title(title, loc="left")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8.5)
    fig.tight_layout()
    return fig


def _save(fig, folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / (name + ".png"), bbox_inches="tight")
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# ================================================================ HTML

CSS = """
:root{--paper:#F4F6F7;--sheet:#FFFFFF;--ink:#17252F;--muted:#5B6B75;--rule:#D3DADF;
--faint:#EDF0F2;--loss:#B4412F;--gain:#2E7A68;--hist:#34566E;--hypo:#86661A}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font:15px/1.55 "Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif}
main{max-width:1080px;margin:0 auto;padding:44px 24px 96px}
h1,h2{font-family:Bahnschrift,"DIN Alternate","Roboto Condensed","Arial Narrow",sans-serif;
font-weight:600;line-height:1.15;letter-spacing:.005em}
h1{font-size:42px;margin:0 0 10px}
h2{font-size:25px;margin:60px 0 10px;padding-top:14px;border-top:3px solid var(--ink)}
h3{font-size:16px;margin:28px 0 8px}
p{max-width:74ch}
.lede{font-size:19px;margin:0 0 8px;max-width:60ch}
.meta,.note,figcaption{color:var(--muted);font-size:13.5px}
.worst{font-size:17px;margin:22px 0 14px}
.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.neg{color:var(--loss)}.pos{color:var(--gain)}
.ladder{background:var(--sheet);border:1px solid var(--rule);border-radius:6px;padding:4px 0}
.rung{display:grid;grid-template-columns:minmax(200px,1.7fr) 96px minmax(150px,2fr) 70px 104px;
gap:14px;align-items:center;padding:8px 18px}
.rung+.rung{border-top:1px solid var(--faint)}
.rung .name{font-weight:600}
.rung .detail{display:block;color:var(--muted);font-size:12.5px;font-weight:400}
.tag{font-size:12px;padding:2px 9px;border-radius:10px;justify-self:start}
.tag.hist{background:#E1EAF0;color:var(--hist)}.tag.hypo{background:#F3EBD6;color:var(--hypo)}
.track{position:relative;height:16px}
.track::before{content:"";position:absolute;left:50%;top:-4px;bottom:-4px;width:1px;background:var(--rule)}
.fill{position:absolute;top:2px;bottom:2px;border-radius:2px}
.fill.neg{right:50%;background:var(--loss)}.fill.pos{left:50%;background:var(--gain)}
.scroll{overflow-x:auto;background:var(--sheet);border:1px solid var(--rule);border-radius:6px;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:14px}
th{text-align:left;font-weight:600;color:var(--muted);font-size:12.5px;padding:10px 12px;
border-bottom:1px solid var(--rule);vertical-align:bottom}
td{padding:8px 12px;border-bottom:1px solid var(--faint);vertical-align:top}
tr:last-child td{border-bottom:0}
th.num{text-align:right;white-space:normal}
.nowrap{white-space:nowrap}
td .detail{display:block;color:var(--muted);font-size:12.5px}
figure{margin:18px 0;background:var(--sheet);border:1px solid var(--rule);border-radius:6px;padding:14px}
figure img{width:100%;height:auto;display:block}
.warn{border-left:4px solid var(--hypo);background:#FBF6EA;padding:12px 16px;border-radius:0 6px 6px 0}
.warn li{margin:4px 0}
@media (max-width:760px){main{padding:28px 16px 64px}h1{font-size:31px}
.rung{grid-template-columns:1fr 76px 96px;gap:10px;padding:8px 12px}.rung .tag,.rung .track{display:none}}
"""


def _e(text):
    return html.escape(str(text))


def _table(headers, rows, numeric):
    """headers: list of str; rows: list of lists of (html, css class); numeric: set of col idx."""
    head = "".join('<th class="num">%s</th>' % _e(h) if i in numeric else "<th>%s</th>" % _e(h)
                   for i, h in enumerate(headers))
    body = ""
    for row in rows:
        cells = ""
        for i, (content, cls) in enumerate(row):
            classes = " ".join(c for c in ("num" if i in numeric else "", cls) if c)
            cells += '<td class="%s">%s</td>' % (classes, content) if classes else "<td>%s</td>" % content
        body += "<tr>%s</tr>" % cells
    return '<div class="scroll"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, body)


def _ladder(hist, scen, summary_mode):
    tests = []
    for name, row in hist["summary"].iterrows():
        detail = "%s to %s" % (row["start"].strftime("%d %b %Y"), row["end"].strftime("%d %b %Y"))
        tests.append((row["portfolio_return"], row["pnl"], name, detail, "hist", "Past crisis"))
    for name, row in scen["summary"].iterrows():
        tests.append((row[summary_mode + "_return"], row[summary_mode + "_pnl"], name,
                      row["shocks"], "hypo", "What if"))
    tests.sort(key=lambda t: t[0])
    scale = max([abs(t[0]) for t in tests] + [1e-9])
    rungs = ""
    for ret, pnl, name, detail, kind, tag in tests:
        cls = sign_class(ret)
        width = 50 * abs(ret) / scale
        rungs += (
            '<div class="rung"><span class="name">%s<span class="detail">%s</span></span>'
            '<span class="tag %s">%s</span>'
            '<span class="track"><span class="fill %s" style="width:%.2f%%"></span></span>'
            '<span class="num %s">%s</span><span class="num %s">%s</span></div>'
            % (_e(name), _e(detail), kind, tag, cls or "pos", width, cls, pct(ret), cls, money(pnl))
        )
    return tests, '<div class="ladder">%s</div>' % rungs


def build_html(portfolio, hist, scen, model, factors, charts, meta):
    summary_mode = meta["summary_mode"]
    tests, ladder = _ladder(hist, scen, summary_mode)
    worst = tests[0] if tests else None
    value = portfolio["value"].sum()

    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width, initial-scale=1">'
             "<title>Portfolio stress test</title><style>%s</style></head><body><main>"
             % (CSS + explorer.CSS)]

    parts.append(
        "<header><h1>Portfolio stress test</h1>"
        '<p class="lede">How a $%s portfolio of %d holdings would fare if %d past crises '
        "happened again, and under %d hypothetical market shocks.</p>"
        '<p class="meta">Prices up to %s. Sensitivities estimated from weekly data, %s to %s. '
        "Report created %s.</p></header>"
        % (format(value, ",.0f"), len(portfolio), len(hist["summary"]), len(scen["summary"]),
           meta["last_price"].strftime("%d %b %Y"), model.window[0].strftime("%d %b %Y"),
           model.window[1].strftime("%d %b %Y"), meta["created"].strftime("%d %b %Y %H:%M")))

    parts.append("<section><h2>Every test, worst first</h2>")
    if worst:
        parts.append('<p class="worst">The worst result in this run is <strong>%s</strong>: '
                     '<span class="num %s">%s</span>, or <span class="num">%s</span>.</p>'
                     % (_e(worst[2]), sign_class(worst[0]), pct(worst[0]), money(worst[1])))
    parts.append(ladder)
    parts.append('<p class="note">Past crises replay what each holding actually did over the '
                 "dates shown. What-if shocks use the %s version of the factor model (see "
                 "below). Bars share one scale, so their lengths compare directly. To try your own "
                 'numbers, use the sliders in <a href="#explore">Try your own shock</a>.</p></section>'
                 % summary_mode)

    # ---- holdings
    by_class = portfolio.groupby("asset_class")["weight"].sum().sort_values(ascending=False)
    rows = [[(_e(t), ""), (_e(r["name"]), ""), (_e(r["asset_class"]), ""),
             ("%.1f%%" % (r["weight"] * 100), ""), ("$" + format(r["value"], ",.0f"), "")]
            for t, r in portfolio.iterrows()]
    parts.append("<section><h2>What the portfolio holds</h2>")
    parts.append("<p>By asset class: %s. Change the holdings in <code>config.py</code>.</p>"
                 % ", ".join("%s %.0f%%" % (_e(c), w * 100) for c, w in by_class.items()))
    parts.append(_table(["Ticker", "What it is", "Asset class", "Weight", "Value"], rows, {3, 4}))
    parts.append("</section>")

    # ---- historical
    hs = hist["summary"]
    if not hs.empty:
        rows = []
        for name, r in hs.iterrows():
            label = _e(name) + ("*" if r["estimated"] else "")
            rows.append([
                ('%s<span class="detail">%s</span>' % (label, _e(r["about"])), ""),
                ("%s<br>%s" % (r["start"].strftime("%d %b %Y"), r["end"].strftime("%d %b %Y")),
                 "nowrap"),
                (str(int(r["trading_days"])), ""),
                (pct(r["spx_move"] / 100 if r["spx_move"] is not None else None), sign_class(r["spx_move"])),
                (bp(r["ust10y_move_bp"]), ""),
                (pct(r["portfolio_return"]), sign_class(r["portfolio_return"])),
                (money(r["pnl"]), sign_class(r["pnl"])),
                (pct(r["max_drawdown"]), sign_class(r["max_drawdown"])),
                ("%s / %s" % (_e(r["worst_holding"]), _e(r["best_holding"])), ""),
            ])
        parts.append("<section><h2>Past crises replayed</h2>")
        parts.append("<p>Each row applies what really happened between the two dates to "
                     "today's weights, holding everything to the end without rebalancing. "
                     "The worst dip is the largest fall from a high point inside the window, "
                     "which can be deeper than the end result.</p>")
        parts.append(_table(["Regime", "Dates", "Trading days", "S&P 500", "US 10Y yield",
                             "Portfolio", "Gain/loss", "Worst dip", "Worst / best holding"],
                            rows, {2, 3, 4, 5, 6, 7}))
        if hs["estimated"].astype(bool).any():
            parts.append('<p class="note">* Some holdings had no prices yet in this period; '
                         "their returns are estimated from the factor model and the factors' "
                         "actual moves.</p>")
        parts.append('<figure><img alt="Heatmap of each holding\'s return in each crisis" '
                     'src="data:image/png;base64,%s"><figcaption>Return of each holding (%%) '
                     "in each crisis. An asterisk marks an estimate.</figcaption></figure>"
                     % charts["regime_heatmap"])
        parts.append('<figure><img alt="Portfolio value path during each crisis" '
                     'src="data:image/png;base64,%s"><figcaption>Portfolio value day by day '
                     "inside each window. All panels share the same vertical scale.</figcaption>"
                     "</figure>" % charts["regime_paths"])
        parts.append('<figure><img alt="Contribution of each asset class in each crisis" '
                     'src="data:image/png;base64,%s"><figcaption>Where each crisis loss came '
                     "from, by asset class. The diamond is the total.</figcaption></figure>"
                     % charts["regime_contributions"])
        parts.append("</section>")

    # ---- scenarios
    ss = scen["summary"]
    rows = [[(_e(name), ""), (_e(r["shocks"]), ""),
             (pct(r["isolated_return"]), sign_class(r["isolated_return"])),
             (money(r["isolated_pnl"]), sign_class(r["isolated_pnl"])),
             (pct(r["correlated_return"]), sign_class(r["correlated_return"])),
             (money(r["correlated_pnl"]), sign_class(r["correlated_pnl"]))]
            for name, r in ss.iterrows()]
    parts.append("<section><h2>Hypothetical shocks</h2>")
    parts.append("<p><strong>Isolated</strong> moves only the factors named in the scenario and "
                 "holds the others flat. <strong>Correlated</strong> also moves the unnamed "
                 "factors by the amount they have typically moved alongside the named shock in "
                 "the estimation period. When the two differ a lot, the answer depends heavily "
                 "on how markets are correlated at the time.</p>")
    parts.append(_table(["Scenario", "Shock", "Isolated return", "Isolated $",
                         "Correlated return", "Correlated $"], rows, {2, 3, 4, 5}))

    im = scen["implied_moves"]
    rows = []
    for name, r in im.iterrows():
        cells = [(_e(name), "")]
        for key, spec in factors.items():
            v = r[key]
            text = bp(v) if spec["kind"] == "yield" else pct(v / 100)
            cells.append((text, sign_class(v)))
        rows.append(cells)
    parts.append("<h3>What the correlated version assumes</h3>")
    parts.append("<p>The full set of factor moves behind each correlated result. The named "
                 "shocks are exactly as you set them; the rest are the model's estimates.</p>")
    parts.append(_table(["Scenario"] + [spec["label"] for spec in factors.values()], rows,
                        set(range(1, len(factors) + 1))))
    parts.append('<figure><img alt="Contribution of each asset class in each scenario" '
                 'src="data:image/png;base64,%s"><figcaption>Where each scenario result comes '
                 "from, by asset class (%s version). The diamond is the total.</figcaption>"
                 "</figure></section>" % (charts["scenario_contributions"], summary_mode))

    # ---- sliders
    parts.append(explorer.build_section(portfolio, model, factors, hist, scen, meta,
                                        _class_colour))

    # ---- betas
    rb = readable_betas(model, factors)
    rows = []
    for ticker, r in rb.iterrows():
        cells = [(_e(ticker), "")]
        for col in rb.columns[:-2]:
            cells.append((signed(r[col], 2), sign_class(round(r[col], 2))))
        cells.append(("%.2f" % r["R squared"], ""))
        cells.append((str(int(r["Weeks of data"])), ""))
        rows.append(cells)
    headers = ["Holding"]
    for key, spec in factors.items():
        headers.append("%s, +10 bp" % spec["label"] if spec["kind"] == "yield"
                       else "%s, +1%%" % spec["label"])
    headers += ["R squared", "Weeks"]
    parts.append("<section><h2>How sensitive each holding is</h2>")
    parts.append("<p>Each number is the holding's typical move, in percent, when that one "
                 "factor moves by the amount in the column heading and the others stay flat. "
                 "They come from a regression of weekly returns on all the factors together. "
                 "R squared shows how much of a holding's weekly movement the factors explain: "
                 "close to 1 means the scenarios describe it well, close to 0 means they miss "
                 "most of what drives it.</p>")
    parts.append(_table(headers, rows, set(range(1, len(headers)))))
    parts.append("</section>")

    # ---- warnings
    warnings = model.warnings + hist["warnings"] + scen["warnings"]
    if warnings:
        parts.append('<section><h2>Please note</h2><div class="warn"><ul>%s</ul></div></section>'
                     % "".join("<li>%s</li>" % _e(w) for w in warnings))

    # ---- method
    parts.append(
        "<section><h2>How this works, and what it leaves out</h2>"
        "<p><strong>Past crises.</strong> For each window the program takes every holding's "
        "adjusted closing price (dividends and coupons included) on the first and last trading "
        "day, and every day in between. Today's weights are applied as if the portfolio had "
        "been bought on the first day and left alone.</p>"
        "<p><strong>What-if shocks.</strong> A regression of each holding's weekly return on "
        "weekly moves in the S&amp;P 500, the 10-year Treasury yield, oil, the dollar and gold "
        "gives its sensitivities. A scenario's result is the sum of sensitivity times shock "
        "across the factors.</p>"
        "<p><strong>Limits to keep in mind.</strong> The model is a straight line: it assumes "
        "an 8% fall is simply eight times a 1% fall, and ignores bond convexity and options. "
        "Sensitivities and correlations come from one period and change over time; in 2022 "
        "stocks and bonds fell together, which did not happen in 2008. The replay uses the "
        "yields and valuations of the past, not today's; a bond fund bought today at a "
        "different yield would earn different income through the same crisis. Everything is "
        "in US dollars, so currency risk for a Hong Kong dollar or other investor is not "
        "shown. Only assets are stressed, not liabilities or cash needs. These results are "
        "for learning and discussion, not investment advice.</p></section>")

    parts.append("</main></body></html>")
    return "".join(parts)


# ================================================================ Excel

def build_workbook_sheets(portfolio, hist, scen, model, factors):
    sheets = {}
    p = portfolio.copy()
    p["weight"] = p["weight"] * 100
    sheets["Portfolio"] = p.rename(columns={"weight": "weight (%)", "value": "value ($)"})

    if not hist["summary"].empty:
        h = hist["summary"].copy()
        for col in ("portfolio_return", "max_drawdown", "worst_day"):
            h[col] = h[col] * 100
        h["start"] = h["start"].dt.date
        h["end"] = h["end"].dt.date
        sheets["Crises"] = h.rename(columns={
            "portfolio_return": "portfolio return (%)", "pnl": "gain/loss ($)",
            "max_drawdown": "worst dip (%)", "worst_day": "worst day (%)",
            "spx_move": "S&P 500 move (%)", "ust10y_move_bp": "US 10Y yield change (bp)"})
        sheets["Crises - holdings (%)"] = hist["asset_returns"] * 100

    s = scen["summary"].copy()
    for mode in ("isolated", "correlated"):
        s[mode + "_return"] = s[mode + "_return"] * 100
    sheets["Scenarios"] = s.rename(columns={
        "isolated_return": "isolated return (%)", "isolated_pnl": "isolated gain/loss ($)",
        "correlated_return": "correlated return (%)", "correlated_pnl": "correlated gain/loss ($)"})
    sheets["Scenarios - corr (%)"] = scen["asset_returns"]["correlated"] * 100
    sheets["Scenarios - isol (%)"] = scen["asset_returns"]["isolated"] * 100
    im = scen["implied_moves"].copy()
    im.columns = ["%s (%s)" % (factors[k]["label"], "bp" if factors[k]["kind"] == "yield" else "%")
                  for k in im.columns]
    sheets["Correlated factor moves"] = im
    sheets["Sensitivities"] = readable_betas(model, factors)
    return sheets


def write_excel(path, sheets):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name[:31])
            sheet = writer.sheets[name[:31]]
            for column in sheet.columns:
                longest = max(len(str(c.value)) if c.value is not None else 0 for c in column)
                sheet.column_dimensions[column[0].column_letter].width = min(max(10, longest + 2), 60)
                for cell in column[1:]:
                    if isinstance(cell.value, float):
                        cell.number_format = "#,##0.00"


# ================================================================ all outputs

def write_outputs(output_dir, portfolio, hist, scen, model, factors, meta):
    """Create charts, the HTML report and the Excel file. Return their paths."""
    _style()
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_dir = output_dir / "charts"
    summary_mode = meta["summary_mode"]
    charts = {}

    if not hist["summary"].empty:
        estimated = {name: [t.strip() for t in row["estimated"].split(",") if t.strip()]
                     for name, row in hist["summary"].iterrows()}
        charts["regime_heatmap"] = _save(chart_heatmap(
            hist["asset_returns"], estimated, "Holding returns in past crises (%)"),
            chart_dir, "crises_heatmap")
        charts["regime_paths"] = _save(chart_paths(hist["paths"]), chart_dir, "crises_paths")
        charts["regime_contributions"] = _save(chart_contributions(
            hist["contributions"], hist["summary"]["portfolio_return"],
            "Past crises: contribution by asset class"), chart_dir, "crises_contributions")
    charts["scenario_contributions"] = _save(chart_contributions(
        scen["contributions"], scen["summary"][summary_mode + "_return"],
        "What-if shocks: contribution by asset class (%s)" % summary_mode),
        chart_dir, "scenarios_contributions")

    html_path = output_dir / "stress_test_report.html"
    html_path.write_text(build_html(portfolio, hist, scen, model, factors, charts, meta),
                         encoding="utf-8")

    excel_path = output_dir / "stress_test_results.xlsx"
    sheets = build_workbook_sheets(portfolio, hist, scen, model, factors)
    try:
        write_excel(excel_path, sheets)
    except PermissionError:
        # Usually the file is open in Excel, which locks it. Save a copy instead.
        excel_path = output_dir / ("stress_test_results_%s.xlsx" % datetime.now().strftime("%H%M%S"))
        write_excel(excel_path, sheets)
        print("The Excel file was open, so the results were saved as %s" % excel_path.name)

    return {"html": html_path, "excel": excel_path, "charts": chart_dir}


def open_in_browser(path):
    try:
        webbrowser.open(path.resolve().as_uri())
    except Exception:  # noqa: BLE001 - opening the browser is a convenience only
        pass
