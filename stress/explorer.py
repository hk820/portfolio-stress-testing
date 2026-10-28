"""The "Try your own shock" section of the HTML report: sliders you can drag.

How it works: Python has already fitted the factor model. We copy its numbers
(each holding's betas, the factors' covariance and the portfolio weights) into
the web page as data, and a small JavaScript program repeats the same sum the
Python code does in scenarios.py every time a slider moves:

    holding return   = sum over factors of (beta x factor move)
    portfolio return = sum over holdings of (weight x holding return)

Because the page only does this arithmetic, the sliders respond instantly, work
without internet, and the report is still one file you can email.
Past crises are not on the sliders: they are what actually happened.
"""

import json

import pandas as pd

from .portfolio import CASH

DEFAULT_RANGE = {"return": (-30, 30, 1), "yield": (-200, 200, 5)}


def build_section(portfolio, model, factors, hist, scen, meta, class_colours):
    data = _page_data(portfolio, model, factors, hist, scen, meta, class_colours)
    # "</" inside a <script> block could end it early, so it is escaped.
    payload = json.dumps(data).replace("</", "<\\/")
    return (
        "<section id=\"explore\"><h2>Try your own shock</h2>"
        "<p>Tick a factor to set its move with its slider. Unticked factors either move "
        "with your shock, by the amount the model expects (correlated), or stay flat "
        "(isolated). Everything recalculates as you drag. The model is a straight line, "
        "so doubling a shock doubles the result.</p>"
        "<div class=\"explorer\">"
        "<div class=\"ex-controls\">"
        "<div class=\"ex-top\">"
        "<label class=\"ex-preset\">Start from <select id=\"ex-preset\"></select></label>"
        "<fieldset class=\"ex-mode\"><legend>Unticked factors</legend>"
        "<label><input type=\"radio\" name=\"ex-mode\" value=\"correlated\"> move with the shock</label>"
        "<label><input type=\"radio\" name=\"ex-mode\" value=\"isolated\"> stay flat</label>"
        "</fieldset></div>"
        "<div id=\"ex-factors\"></div>"
        "</div>"
        "<div class=\"ex-result\" aria-live=\"polite\">"
        "<p class=\"ex-total\"><span id=\"ex-ret\" class=\"num\"></span>"
        "<span id=\"ex-pnl\" class=\"num\"></span></p>"
        "<p class=\"note\" id=\"ex-hint\"></p>"
        "<div id=\"ex-classes\"></div>"
        "<div class=\"scroll\"><table><thead><tr><th>Holding</th><th class=\"num\">Weight</th>"
        "<th class=\"num\">Return</th><th class=\"num\">Gain/loss</th></tr></thead>"
        "<tbody id=\"ex-holdings\"></tbody></table></div>"
        "</div></div>"
        "<noscript><p class=\"warn\">Turn on JavaScript in your browser to use the sliders.</p>"
        "</noscript></section>"
        "<script type=\"application/json\" id=\"ex-data\">" + payload + "</script>"
        "<script>" + SCRIPT + "</script>"
    )


def _page_data(portfolio, model, factors, hist, scen, meta, class_colours):
    keys = list(factors)
    ranges = meta.get("slider_ranges", {})
    factor_rows = []
    for key in keys:
        spec = factors[key]
        low, high, step = ranges.get(key, DEFAULT_RANGE[spec["kind"]])
        factor_rows.append({"key": key, "label": spec["label"], "kind": spec["kind"],
                            "min": low, "max": high, "step": step})

    holdings = []
    for ticker, row in portfolio.iterrows():
        betas = [0.0] * len(keys) if ticker == CASH else \
            [float(model.betas.loc[ticker, k]) for k in keys]
        holdings.append({"ticker": ticker, "name": row["name"], "cls": row["asset_class"],
                         "weight": float(row["weight"]), "betas": betas})

    # One fixed scale for the asset-class bars, so a bar visibly grows as you
    # drag a slider further (a scale that followed the slider would not).
    biggest = [scen["contributions"].abs().to_numpy().max()]
    if not hist["contributions"].empty:
        biggest.append(hist["contributions"].abs().to_numpy().max())
    classes = list(dict.fromkeys(portfolio["asset_class"]))

    return {
        "factors": factor_rows,
        "holdings": holdings,
        "cov": model.covariance.loc[keys, keys].to_numpy().tolist(),
        "presets": [{"name": s["name"], "shocks": s["shocks"]} for s in meta.get("presets", [])],
        "value": float(portfolio["value"].sum()),
        "mode": meta["summary_mode"],
        "barScale": float(max(max(biggest), 0.01)),
        "classes": [{"name": c, "colour": class_colours(c, i)} for i, c in enumerate(classes)],
    }


CSS = """
.explorer{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px;
background:var(--sheet);border:1px solid var(--rule);border-radius:6px;padding:20px}
.ex-top{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:flex-end;margin-bottom:14px}
.ex-preset{flex:1 1 240px;min-width:0}
.ex-preset select{display:block;width:100%;margin-top:4px;font:inherit;font-size:14px;padding:5px 8px;
border:1px solid var(--rule);border-radius:4px;background:#fff;color:var(--ink);max-width:100%}
.ex-mode{border:0;padding:0;margin:0;font-size:14px}
.ex-mode legend{padding:0;margin-bottom:4px}
.ex-mode label{margin-right:14px;white-space:nowrap}
.ex-row{display:grid;grid-template-columns:minmax(120px,1.2fr) minmax(110px,2fr) 72px;
gap:4px 12px;align-items:center;padding:9px 0;border-top:1px solid var(--faint)}
.ex-set{font-size:14px;font-weight:600;cursor:pointer}
.ex-row:not(.is-set) .ex-set{font-weight:400;color:var(--muted)}
.ex-row input[type=range]{width:100%;accent-color:var(--ink);cursor:pointer}
.ex-row input[type=range]:disabled{opacity:.4;cursor:default}
.ex-val{font-size:14px}
.ex-note{grid-column:2 / 4;font-size:12px;color:var(--muted);margin-top:-4px}
.ex-total{margin:0 0 2px;display:flex;flex-wrap:wrap;gap:4px 16px;align-items:baseline}
#ex-ret{font-family:Bahnschrift,"DIN Alternate","Roboto Condensed","Arial Narrow",sans-serif;
font-size:44px;font-weight:600;line-height:1.1}
#ex-pnl{font-size:20px}
.ex-bar{display:grid;grid-template-columns:130px minmax(80px,1fr) 64px;gap:10px;align-items:center;
font-size:13.5px;padding:4px 0}
.ex-bar .track{height:14px}
.ex-bar .fill.over::after{content:"";position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink)}
.ex-bar .fill.neg.over::after{left:0}.ex-bar .fill.pos.over::after{right:0}
#ex-classes{margin:10px 0 6px}
.ex-result .scroll{margin-top:10px}
.ex-result td{padding:6px 12px}
@media (max-width:860px){.explorer{grid-template-columns:minmax(0,1fr);padding:14px}}
@media (max-width:480px){.ex-row{grid-template-columns:1fr 72px}.ex-row .ex-val{grid-row:1;grid-column:2;text-align:right}
.ex-row input[type=range]{grid-column:1 / 3}
.ex-note{grid-column:1 / 3}.ex-bar{grid-template-columns:100px 1fr 60px}}
"""


# The JavaScript mirrors scenarios.implied_factor_moves and run_scenarios.
# Units follow config.py: percent for price factors, basis points for yields.
SCRIPT = r"""
(function () {
  var data = JSON.parse(document.getElementById("ex-data").textContent);
  var F = data.factors, H = data.holdings, n = F.length;
  var MINUS = "\u2212";
  var state = { mode: data.mode, set: F.map(function () { return false; }),
                value: F.map(function () { return 0; }) };
  var rows = [], holdingCells = [], classBars = {};

  function signed(x, dp) {
    var r = Number(x.toFixed(dp));
    if (r === 0) { return (0).toFixed(dp); }
    return (r > 0 ? "+" : MINUS) + Math.abs(r).toFixed(dp);
  }
  function pct(x) { return signed(x * 100, 1) + "%"; }
  function money(x) {
    var r = Math.round(x);
    if (r === 0) { return "$0"; }
    return (r < 0 ? MINUS : "+") + "$" + Math.abs(r).toLocaleString("en-US");
  }
  function showFactor(i, v) { return F[i].kind === "yield" ? signed(v, 0) + " bp" : signed(v, 1) + "%"; }
  function toModel(i, v) { return F[i].kind === "yield" ? v : v / 100; }
  function toUser(i, m) { return F[i].kind === "yield" ? m : m * 100; }
  function sign(x) { return Math.abs(x) < 1e-9 ? "" : (x < 0 ? "neg" : "pos"); }
  function clamp(i, v) { return Math.min(F[i].max, Math.max(F[i].min, v)); }
  function snap(i, v) { var s = F[i].step; return clamp(i, Math.round(v / s) * s); }

  // Solve A x = b by Gaussian elimination (A is small: at most a few factors).
  function solve(A, b) {
    var m = A.length, M = A.map(function (row, i) { return row.concat([b[i]]); });
    for (var c = 0; c < m; c++) {
      var p = c;
      for (var r = c + 1; r < m; r++) { if (Math.abs(M[r][c]) > Math.abs(M[p][c])) { p = r; } }
      var tmp = M[c]; M[c] = M[p]; M[p] = tmp;
      if (Math.abs(M[c][c]) < 1e-18) { return null; }
      for (var r2 = 0; r2 < m; r2++) {
        if (r2 === c) { continue; }
        var f = M[r2][c] / M[c][c];
        for (var k = c; k <= m; k++) { M[r2][k] -= f * M[c][k]; }
      }
    }
    return M.map(function (row, i) { return row[m] / row[i]; });
  }

  // Factor moves in model units: the ticked ones as set, the rest either
  // flat or Cov(other, ticked) x Cov(ticked)^-1 x ticked shocks.
  function factorMoves() {
    var named = [], others = [], moves = [];
    for (var i = 0; i < n; i++) {
      moves.push(state.set[i] ? toModel(i, state.value[i]) : 0);
      (state.set[i] ? named : others).push(i);
    }
    if (state.mode === "correlated" && named.length && others.length) {
      var A = named.map(function (a) { return named.map(function (b) { return data.cov[a][b]; }); });
      var x = solve(A, named.map(function (a) { return moves[a]; }));
      if (x) {
        others.forEach(function (o) {
          moves[o] = named.reduce(function (s, a, j) { return s + data.cov[o][a] * x[j]; }, 0);
        });
      }
    }
    return moves;
  }

  function update() {
    var moves = factorMoves(), anySet = state.set.some(Boolean);
    rows.forEach(function (row, i) {
      var shown = state.set[i] ? state.value[i] : toUser(i, moves[i]);
      row.el.classList.toggle("is-set", state.set[i]);
      row.box.checked = state.set[i];
      row.slider.disabled = !state.set[i];
      row.slider.value = state.set[i] ? state.value[i] : clamp(i, shown);
      row.val.textContent = showFactor(i, shown);
      row.val.className = "ex-val num " + sign(shown);
      row.note.textContent = state.set[i] ? "" :
        (state.mode === "correlated" && anySet ? "estimated from your shock" : "held flat");
    });

    var total = 0, byClass = {};
    H.forEach(function (h, j) {
      var r = h.betas.reduce(function (s, b, i) { return s + b * moves[i]; }, 0);
      r = Math.max(r, -1);  // a fund you own outright cannot lose more than 100%
      var contribution = h.weight * r;
      total += contribution;
      byClass[h.cls] = (byClass[h.cls] || 0) + contribution;
      var cells = holdingCells[j];
      cells.ret.textContent = pct(r); cells.ret.className = "num " + sign(r);
      cells.pnl.textContent = money(contribution * data.value);
      cells.pnl.className = "num " + sign(contribution);
    });

    var ret = document.getElementById("ex-ret"), pnl = document.getElementById("ex-pnl");
    ret.textContent = pct(total); ret.className = "num " + sign(total);
    pnl.textContent = money(total * data.value); pnl.className = "num " + sign(total);
    document.getElementById("ex-hint").textContent = anySet ?
      "Portfolio return, and its gain or loss on $" + Math.round(data.value).toLocaleString("en-US") + "." :
      "Tick at least one factor to set a shock.";

    data.classes.forEach(function (c) {
      var v = byClass[c.name] || 0, bar = classBars[c.name];
      var width = Math.min(50, 50 * Math.abs(v) / data.barScale);
      bar.fill.className = "fill " + (v < 0 ? "neg" : "pos") + (50 * Math.abs(v) / data.barScale > 50 ? " over" : "");
      bar.fill.style.width = width.toFixed(2) + "%";
      bar.fill.style.background = c.colour;
      bar.val.textContent = signed(v * 100, 1) + " pp";
      bar.val.className = "num " + sign(v);
    });
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined) { e.textContent = text; }
    return e;
  }

  // ---- build the factor rows
  var box = document.getElementById("ex-factors");
  F.forEach(function (f, i) {
    var row = el("div", "ex-row"), label = el("label", "ex-set"), check = el("input");
    check.type = "checkbox";
    label.appendChild(check); label.appendChild(document.createTextNode(" " + f.label));
    var slider = el("input");
    slider.type = "range"; slider.min = f.min; slider.max = f.max; slider.step = f.step;
    slider.setAttribute("aria-label", f.label + (f.kind === "yield" ? " change in basis points" : " change in percent"));
    var val = el("span", "ex-val num"), note = el("span", "ex-note");
    row.appendChild(label); row.appendChild(slider); row.appendChild(val); row.appendChild(note);
    box.appendChild(row);
    check.addEventListener("change", function () {
      if (check.checked) {  // start the slider where the model had it
        state.value[i] = snap(i, toUser(i, factorMoves()[i]));
      }
      state.set[i] = check.checked;
      document.getElementById("ex-preset").value = "";
      update();
    });
    slider.addEventListener("input", function () {
      state.value[i] = Number(slider.value);
      document.getElementById("ex-preset").value = "";
      update();
    });
    rows.push({ el: row, box: check, slider: slider, val: val, note: note });
  });

  // ---- presets from SCENARIOS in config.py
  var select = document.getElementById("ex-preset");
  select.appendChild(el("option", "", "Your own settings")).value = "";
  data.presets.forEach(function (p, k) { select.appendChild(el("option", "", p.name)).value = String(k); });
  select.appendChild(el("option", "", "Clear all")).value = "clear";
  function applyPreset(key) {
    F.forEach(function (f, i) {
      var shocks = key === "clear" ? {} : data.presets[Number(key)].shocks;
      state.set[i] = Object.prototype.hasOwnProperty.call(shocks, f.key);
      state.value[i] = state.set[i] ? clamp(i, shocks[f.key]) : 0;
    });
  }
  select.addEventListener("change", function () {
    if (select.value !== "") { applyPreset(select.value); }
    if (select.value === "clear") { select.value = ""; }
    update();
  });

  // ---- mode switch
  document.querySelectorAll("input[name=ex-mode]").forEach(function (radio) {
    radio.checked = radio.value === state.mode;
    radio.addEventListener("change", function () { state.mode = radio.value; update(); });
  });

  // ---- asset-class bars and holdings table
  var classBox = document.getElementById("ex-classes");
  data.classes.forEach(function (c) {
    var bar = el("div", "ex-bar"), track = el("span", "track"), fill = el("span", "fill");
    track.appendChild(fill);
    var val = el("span", "num");
    bar.appendChild(el("span", "", c.name)); bar.appendChild(track); bar.appendChild(val);
    classBox.appendChild(bar);
    classBars[c.name] = { fill: fill, val: val };
  });
  var body = document.getElementById("ex-holdings");
  H.forEach(function (h) {
    var tr = el("tr"), name = el("td");
    name.appendChild(document.createTextNode(h.ticker));
    name.appendChild(el("span", "detail", h.name));
    var ret = el("td", "num"), pnl = el("td", "num");
    tr.appendChild(name); tr.appendChild(el("td", "num", (h.weight * 100).toFixed(1) + "%"));
    tr.appendChild(ret); tr.appendChild(pnl); body.appendChild(tr);
    holdingCells.push({ ret: ret, pnl: pnl });
  });

  // Start from the first saved scenario, so the page never opens empty.
  if (data.presets.length) { applyPreset("0"); select.value = "0"; }
  update();
})();
"""
