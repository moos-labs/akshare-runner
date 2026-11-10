# akshare-runner

Runs [AKShare](https://akshare.akfamily.xyz/) data fetches on GitHub
Actions, where the commands to execute live in a repository **Actions
variable** — not in code.

AKShare is a Chinese open-source financial-data interface library: it
scrapes public Chinese (and some international) financial sources —
Eastmoney, Sina, THS and others — and exposes them as simple Python
functions returning pandas DataFrames (A-shares, US/HK stocks, futures,
funds, macro data, and more).

## The pattern (one repo per tool)

1. **Edit the commands**: repo *Settings → Secrets and variables → Actions →
   Variables* → set the `COMMANDS` variable to whatever shell commands this
   run should execute (multi-line works). The same can be done through the
   GitHub API (`PUT /repos/{owner}/{repo}/actions/variables/COMMANDS`).
2. **Trigger manually**: *Actions* tab → “Run analysis” → *Run workflow*
   (or `POST /repos/{owner}/{repo}/actions/workflows/run.yml/dispatches`).
   The workflow has **no other triggers** — it runs only when dispatched.
3. **Collect results**: the workflow uploads everything under `results/` as
   the `results` build artifact (`if: always()`, so partial results survive
   a failing step). Download it from the run page or via the API.

The workflow itself is generic: checkout → Python 3.11 → `pip install -r
requirements.txt` → run `${{ vars.COMMANDS }}` → upload `results/`.
To run a different fetch, change the variable — not the workflow.

## Multi-market by design

Nothing in the workflow or the runner pattern is tied to one exchange.
Scripts take the **ticker symbol and parameters as inputs** (CLI args
and/or the `COMMANDS` variable), so the same repo can fetch an A-share
today and a US stock tomorrow — only the inputs change.

## Pilot: Moutai (600519) + Apple (AAPL)

Pilot `COMMANDS` value:

```sh
mkdir -p results
python scripts/fetch.py 2>&1 | tee results/run.log
```

`scripts/fetch.py` (defaults are the pilot; override with `--a-symbol`,
`--us-symbol`, `--days`, `--adjust`, `--skip-a` / `--skip-us`):

- **A-share**: daily history for `600519` (Kweichow Moutai) for roughly
  the last year via `ak.stock_zh_a_hist`.
- **US**: daily history for AAPL via `ak.stock_us_hist`, using AKShare's
  US symbol format `105.AAPL` (`<market code>.<ticker>`).

Each attempt is independent: on success it saves a CSV under `results/`
and records rows, date range and first/last close; on failure it records
the exact exception. Either way it writes `results/summary.json` with
both verdicts. Note that AKShare scrapes Chinese sources, so behaviour
from a datacenter IP (the GitHub runner) may differ from a residential
connection — a clean failure recorded in `summary.json` is itself a
finding.
