import argparse
import json
import sys
from pathlib import Path

from .client import Client
from .core import audit, discover, plan, public_report, render


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only GitHub achievement evidence and contribution opportunities")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("audit", help="Inspect public PR counts and repository stars")
    a.add_argument("username")
    a.add_argument("--baseline", help="Optional local, manually verified achievement JSON")
    a.add_argument("--auth-gh", action="store_true", help="Use existing GitHub CLI authentication")
    d = sub.add_parser("discover", help="Find bounded public contribution opportunities")
    d.add_argument("--repo", action="append", required=True, help="OWNER/REPO; repeat up to five times")
    d.add_argument("--limit", type=int, default=5)
    d.add_argument("--auth-gh", action="store_true", help="Required for GitHub Discussions")
    p = sub.add_parser("plan", help="Choose up to three opportunities fitting a time budget")
    p.add_argument("input", help="Opportunity JSON report")
    p.add_argument("--minutes", type=int, default=45)
    r = sub.add_parser("report", help="Render an existing public JSON report")
    r.add_argument("input")
    demo = sub.add_parser("demo", help="Render a synthetic offline example")
    for cmd in (a, d, p, r, demo):
        cmd.add_argument("--format", choices=("markdown", "json"), default="markdown")
        cmd.add_argument("--output", help="Output file; defaults to stdout")
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            data = audit(Client(args.auth_gh), args.username, read(args.baseline) if args.baseline else None)
        elif args.command == "discover":
            data = discover(Client(args.auth_gh), args.repo, args.limit)
        elif args.command == "plan":
            data = plan(read(args.input), args.minutes)
        elif args.command == "report":
            data = read(args.input)
        else:
            data = {"schema_version": 1, "kind": "audit", "scope": "public", "username": "example-user",
                    "observed_at": "Synthetic offline example", "achievements": [], "warnings": [],
                    "authored_merged_prs": {"count": 4, "completeness": "synthetic_example"},
                    "repositories": [{"name": "example-user/example-project", "stars": 7,
                        "url": "https://github.com/example-user/example-project", "visibility": "public"}],
                    "repositories_completeness": "synthetic_example"}
        data = public_report(data)
        rendered = render(data)
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else rendered
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"gh-pro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
