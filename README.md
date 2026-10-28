# Portfolio Stress Testing and Scenario Analysis

This project asks a simple risk question: if a past crisis happened again tomorrow, or if markets were hit by a shock such as "the S&P 500 falls 8%", how much would a portfolio of stocks, bonds, commodities and real estate gain or lose? You will learn the two standard ways risk teams answer it: replaying history, and a factor model for shocks that have not happened yet.

Created by Ken Choi. Free to copy, change and share under the MIT License (see [LICENSE](LICENSE)).

## What it does

You describe a portfolio in `config.py` (by default, $1,000,000 spread over 10 exchange-traded funds plus some cash). When you click Run, the program:

1. **Downloads daily prices** for those funds and for five market "factors" (S&P 500, US 10-year Treasury yield, Brent oil, US dollar index, gold) from Yahoo Finance, going back to 2007.
2. **Replays past crises** on today's portfolio: the Global Financial Crisis, the 2011 euro debt crisis, the 2013 taper tantrum, the Q4 2018 sell-off, the Covid-19 crash, the 2022 inflation and rate hikes, the 2024 yen carry-trade unwind and the 2025 US tariff shock.
3. **Runs hypothetical shocks**, such as "S&P 500 falls 8%", "US 10-year yield rises 50 bp" and "stagflation: stocks −10%, yields +75 bp, oil +25%". Each is shown two ways: *isolated* (only the named factors move) and *correlated* (the other factors move the way they usually have alongside the shock).
4. **Shows the results**: a short summary in the terminal, then a report opens in your web browser. Everything is also saved in the `output` folder.
5. **Lets you try your own shock**: in the report's *Try your own shock* section, tick a factor and drag its slider. The portfolio's result, each asset class and each holding update as you drag. The sliders work offline, inside the saved report.

| File in `output/` | What it is |
|---|---|
| `stress_test_report.html` | The full report: every test ranked worst first, sliders to try your own shock, tables, charts, and an explanation of the method. A single file you can email. |
| `stress_test_results.xlsx` | Every number, one sheet per table, for checking or further analysis in Excel. |
| `charts/` | The charts as PNG images, ready for slides. |
| `cache/prices.csv` | The downloaded prices, reused for 24 hours so reruns are fast. |

## Prepare your computer (one time only)

You do this once per computer. After that, every project only needs the steps in the next section.

1. **Install Python** (version 3.10 or newer) from <https://www.python.org/downloads/>.
   On Windows, on the first screen of the installer, tick **Add python.exe to PATH** before clicking Install.
   If the last screen offers **Disable path length limit**, click it. It prevents rare install errors with long folder paths.
2. **Install Git** from <https://git-scm.com/downloads>. The default options are fine.
3. **Install VS Code** from <https://code.visualstudio.com/>.
4. **Install the Python extension in VS Code.** Open VS Code, press `Ctrl+Shift+X`, search for **Python**, and install the one published by Microsoft.
5. **Tell Git your name and email.** In VS Code press ``Ctrl+` `` to open the terminal, then type these two lines, pressing Enter after each. Use the email of your GitHub account.
   ```
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
6. **Create a free GitHub account** at <https://github.com/> (only needed if you want to publish your own version).

## Run this project

1. **Get the project.** Download the zip file. (On GitHub: click the green **Code** button, then **Download ZIP**.)
2. **Extract it** anywhere you like, for example your Desktop: right-click the zip, choose **Extract All...**, then click **Extract**. (On a Mac, double-click the zip.)
   This gives you a folder named `portfolio-stress-testing`. Your project folder is the one that contains `main.py`.
   (A zip downloaded from GitHub has one extra folder inside, named `portfolio-stress-testing-main`. Use that inner folder.)
3. **Open the folder in VS Code:** File > Open Folder, choose the folder that contains `main.py`. If VS Code asks whether you trust the authors, click **Yes**.
4. **Open `main.py`** and click the **Run** button (the triangle at the top right).
5. **First run of this project only:** wait a few minutes while it installs what it needs. Later runs start straight away.

You need an internet connection the first time, to download the prices. This project does not need an API key.

## Try your own portfolio and scenarios

Open `config.py`. It has three sections, each explained in its comments:

- **PORTFOLIO**: each line is a Yahoo Finance ticker with a weight. Weights must add up to 1 (for example 0.30 is 30%). Use `CASH` for money that earns nothing. Look up tickers on <https://finance.yahoo.com>.
- **REGIMES**: past periods to replay, each with a start and end date. Add your own, for example the 2015 China devaluation.
- **SCENARIOS**: shocks to the factors. Stock, oil, dollar and gold shocks are in percent (`-8` means −8%). The yield shock is in basis points (`50` means +0.50%).
- **SLIDER_RANGES**: how far each slider in the report can go. Every scenario in SCENARIOS also appears in the report's *Start from* menu.

Save the file and click Run again. If you added a new ticker, the program downloads its prices automatically.

## How it works

**Replaying a crisis.** For each window, the program takes every fund's actual price at the start, the end and every day in between. Prices are adjusted, so dividends and bond coupons are included. Today's weights are applied as if the portfolio had been bought on the first day and left alone. If a fund did not exist yet, its path is estimated from the factor model, and the report marks it with an asterisk.

**A what-if shock.** For each fund, a regression of its weekly return on the weekly moves of the five factors (over the last 5 years) gives its sensitivities, or "betas". A scenario's result is each beta times its factor's shock, added up. The *correlated* version fills in the factors you did not name with their expected move given the ones you did, using how the factors moved together in the same 5 years.

**What it leaves out.** The model is a straight line, so a 20% crash is treated as twenty 1% falls. Correlations change over time: in 2022, stocks and bonds fell together, which did not happen in 2008. Replays use the yields and prices of the past, not today's. Everything is in US dollars, so currency risk for a Hong Kong dollar investor is not shown. Only assets are stressed, not liabilities. The results are for learning, not investment advice.

## Project files

| File or folder | What it is | Should you change it? |
|---|---|---|
| `main.py` | The program. The only file you run. | Yes, this is where you experiment. |
| `config.py` | The portfolio, the crises, the scenarios and the model settings. No secrets. | Yes, this is the main file to edit. |
| `stress/portfolio.py` | Reads and checks the holdings. | Only if you want to learn how it works. |
| `stress/data.py` | Downloads prices from Yahoo Finance and caches them. | Only if you want to learn how it works. |
| `stress/scenarios.py` | The factor model and the what-if shocks. | Yes, if you want to try a different model. |
| `stress/historical.py` | Replays past crises. | Yes, if you want to change the replay rules. |
| `stress/report.py` | The terminal summary, charts, HTML report and Excel file. | Yes, to change how results look. |
| `stress/explorer.py` | The report's sliders: puts the model's numbers in the page, and a small JavaScript program recalculates as you drag. | Yes, if you want to learn how the sliders work. |
| `tests/test_engine.py` | Checks the maths using made-up prices. No internet needed. | Add tests if you change the maths. |
| `bootstrap.py` | Sets everything up automatically when `main.py` starts. | No. |
| `requirements.txt` | The list of packages the project needs. | Only to add a package. The next run installs it. |
| `output/` | Created when you run. Report, Excel file, charts and cached prices. | No. Delete it to start fresh. |
| `.venv/` | Created on the first run. Holds the installed packages. | No. Delete it to reinstall from scratch. |
| `README.md` | This guide. | Yes, when you publish your own version. |
| `LICENSE` | The MIT License. | Keep it (see below). |
| `.gitignore` | Tells Git which files never to upload. | No. |
| `.vscode/` | Recommends the Python extension to VS Code. | No. |

To run the tests, type this in the VS Code terminal and press Enter: `.venv\Scripts\python -m unittest discover tests` (Mac: `.venv/bin/python -m unittest discover tests`).

To read this README nicely formatted inside VS Code, open it and press `Ctrl+Shift+V`.

## Publish your own version to GitHub

You are welcome to change this project and publish your own version. Use VS Code, not the GitHub website:

1. Open **Source Control** in VS Code (`Ctrl+Shift+G`).
2. Click **Publish to GitHub**. If asked, sign in to GitHub and allow VS Code.
3. Choose a **public** or **private** repository.
4. If VS Code shows a list of files to include, keep them all ticked. The `.venv` and `output` folders are left out automatically because of `.gitignore`, so downloaded prices are never uploaded.
5. After later changes: in Source Control, type a short message describing the change, click **Commit**, then **Sync Changes**.

**Do not** use **Add file > Upload files** on the GitHub website. It uploads everything you drag in and ignores `.gitignore`.

The MIT License asks that you keep the `LICENSE` file and its copyright line. You may add your own name below it.

## Troubleshooting

| What you see | What to do |
|---|---|
| Setup stops with a message about a long path, "Access is denied" or a file "used by another process" | Follow the advice it prints. Usually: give the project folder a shorter name, or extract the zip to another folder, then run `main.py` again. |
| Clicking Run opens the Microsoft Store, or says Python was not found | Install Python from python.org (see [Prepare your computer](#prepare-your-computer-one-time-only)), tick **Add python.exe to PATH**, then restart VS Code. |
| "Installing packages failed" | Check your internet connection and run `main.py` again. It continues where it stopped. |
| "Yahoo Finance returned no prices for ..." | Check your internet connection and the spelling of the ticker in `config.py`. Yahoo may also be limiting requests: wait 10-15 minutes and run again. |
| "The weights in PORTFOLIO add up to ..." | Change the weights in `config.py` so they add up to exactly 1. |
| "... has only N weeks of prices" | That fund is too new for the model. Pick one with at least a few years of history. |
| You want fresh prices before the 24 hours are up | In the VS Code terminal type `python main.py --refresh` and press Enter. |
| "The Excel file was open, so the results were saved as ..." | Close the Excel file before running. The results were saved under a new name. |
| The report did not open in the browser | Open `output/stress_test_report.html` yourself by double-clicking it. |
| The sliders do nothing | JavaScript is switched off in your browser. Turn it on, or open the report in another browser. |
| Wavy yellow lines under `import` lines | Harmless. To remove them: `Ctrl+Shift+P`, type **Python: Select Interpreter**, choose the one marked `.venv`. |
| Something is badly broken | Delete the `.venv` folder and run `main.py` again to rebuild it. |

## License

MIT License. Copyright (c) 2026 Ken Choi. See [LICENSE](LICENSE).
