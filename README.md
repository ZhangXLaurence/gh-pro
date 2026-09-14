# gh-pro

**Find your next useful GitHub contribution. Keep achievement evidence honest.**

gh-pro is a small, read-only Python CLI that reports public contribution activity, tracks manually confirmed achievements, and finds open issues and unanswered project discussions. It runs locally, uses no model API, and has no runtime Python dependencies.

[中文说明](docs/README.zh-CN.md) · [How the rules work](docs/achievement-rules.md) · [Contributing](CONTRIBUTING.md)

## Try it in a minute

Python 3.10 or later is required. The offline demo needs no GitHub account or network connection.

```sh
git clone https://github.com/ZhangXLaurence/gh-pro.git
cd gh-pro
python3 -m gh_pro demo
```

Inspect a public account without authentication:

```sh
python3 -m gh_pro audit octocat
```

For higher API rate limits and Discussion discovery, use your existing [GitHub CLI](https://cli.github.com/) login:

```sh
python3 -m gh_pro audit YOUR_USERNAME --auth-gh
python3 -m gh_pro discover --repo OWNER/REPO --auth-gh
```

Replace `YOUR_USERNAME` and `OWNER/REPO` with the account and public repository you want to inspect. Authentication is managed by `gh`; gh-pro does not store tokens. All API operations are reads. Existing CLI credentials are not modified or narrowed by this program.

## What it does

| Command | Result |
| --- | --- |
| `audit USER` | Public authored-and-merged PR search count; stars for each owned, non-fork public repository |
| `discover --repo OWNER/REPO` | Open, unassigned `good first issue` candidates; with `--auth-gh`, recent unanswered Discussions in answerable categories |
| `plan opportunities.json --minutes 45` | Up to three observed opportunities fitting a rough time estimate |
| `report audit.json` | Markdown rendering of an existing public JSON report |
| `demo` | Clearly labelled synthetic report, entirely offline |

Every command accepts `--format markdown` or `--format json`, and `--output PATH`. Output goes to the terminal by default; an explicit output path is overwritten. Keep personal reports outside a public repository. `reports/` is ignored in this checkout.

```sh
mkdir -p reports
python3 -m gh_pro discover --repo OWNER/REPO --auth-gh --format json --output reports/opportunities.json
python3 -m gh_pro plan reports/opportunities.json --minutes 45
python3 -m gh_pro audit YOUR_USERNAME --format json --output reports/audit.json
python3 -m gh_pro report reports/audit.json
```

Repeat `--repo` for up to five repositories. Results are a bounded sample, not an exhaustive search. Read the issue or discussion and its linked work before contributing. No suitable candidate is a valid result.

## Confirming achievements

GitHub awards achievements. An API count alone does not prove an award or a tier upgrade. Record badges you have actually checked on your profile in a local JSON file:

```json
{
  "username": "YOUR_USERNAME",
  "observed_on": "2026-09-15",
  "achievements": [
    {"slug": "pull-shark", "status": "earned"},
    {"slug": "galaxy-brain", "status": "not_publicly_visible"}
  ]
}
```

```sh
python3 -m gh_pro audit YOUR_USERNAME --baseline baseline.json
```

Accepted statuses are `earned`, `not_publicly_visible`, and `unknown`. A missing public badge may have been hidden. The baseline confirmation date stays separate from the API observation time. Unknown extra baseline fields are discarded.

## Boundaries in v0.1

- Private and fork repositories are excluded from repository reports. API failures produce unknown or partial observations, never fabricated zeros.
- Stars are reported per repository, not summed toward Starstruck. Current ownership does not establish who originally created a repository.
- Achievement thresholds are [community observations](https://github.com/Schweinepriester/github-profile-achievements), not a supported GitHub award API. Hidden badges and award-processing delays remain unknown.
- Discovery samples at most 10 labelled issues and 20 recent discussions per repository. It does not determine whether a linked PR already solves an issue. Estimates are heuristic, not acceptance probabilities.
- Galaxy Brain answer totals, coauthor totals, automatic badge scraping, and background monitoring are not implemented.
- The GitHub official Community is excluded because [achievements are disabled there](https://github.com/orgs/community/discussions/106536).
- The tool does not post comments, open or merge PRs, mark answers, request stars, or purchase sponsorships. It helps you find work and record evidence.
- A run has a 35-request budget and bounded timeouts. There are no automatic retries or persistent response caches. Review the report's limitations after a partial failure.

The public report format is intended for public data. Importing an arbitrary file does not automatically classify its prose as public: inspect any hand-edited report before sharing it. Unknown fields and entries explicitly marked private are omitted from both export formats.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 -m gh_pro demo
```

An optional editable install exposes the shorter `gh-pro` command:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/gh-pro demo
```

The distribution name is `gh-pro-contributor`; this project is currently installed from its repository, not from a published PyPI release. MIT licensed.
