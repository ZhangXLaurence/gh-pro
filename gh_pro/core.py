"""Public observations and explainable next steps; not official award counters."""

import copy
import re
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

from .client import APIError, login, repository

RULE_SOURCE = "https://github.com/Schweinepriester/github-profile-achievements"
RULES = {
    "pull-shark": {"name": "Pull Shark", "thresholds": [2, 16, 128, 1024]},
    "pair-extraordinaire": {"name": "Pair Extraordinaire", "thresholds": [1, 10, 24, 48]},
    "galaxy-brain": {"name": "Galaxy Brain", "thresholds": [2, 8, 16, 32]},
    "starstruck": {"name": "Starstruck", "thresholds": [16, 128, 512, 4096]},
    "quickdraw": {"name": "Quickdraw", "thresholds": []},
    "yolo": {"name": "YOLO", "thresholds": []},
    "public-sponsor": {"name": "Public Sponsor", "thresholds": []},
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_url(url):
    """Only render clean, public GitHub links; remote text is never executable."""
    if not isinstance(url, str) or re.search(r"[\s\x00-\x1f\x7f<>\\]", url):
        return ""
    try:
        p = urlparse(url)
        if p.scheme != "https" or p.netloc != "github.com":
            return ""
        return url.replace("(", "%28").replace(")", "%29")
    except ValueError:
        return ""


def confirmed_badges(baseline, username):
    if baseline is None:
        return []
    if baseline.get("username", "").lower() != username.lower():
        raise ValueError("Baseline belongs to a different GitHub user")
    result = []
    for item in baseline.get("achievements", []):
        if item.get("slug") not in RULES:
            continue
        status = item.get("status", "unknown")
        if status not in ("earned", "not_publicly_visible", "unknown"):
            status = "unknown"
        result.append({"slug": item["slug"], "status": status,
                       "observed_on": baseline.get("observed_on", "unknown")})
    return result


def audit(client, username, baseline=None):
    login(username)
    report = {"schema_version": 1, "kind": "audit", "username": username,
              "observed_at": now(), "scope": "public", "warnings": [],
              "achievements": confirmed_badges(baseline, username),
              "rules_source": RULE_SOURCE, "rules_verified_on": "2026-09-15",
              "authored_merged_prs": {"count": None, "completeness": "unavailable"},
              "repositories": [], "repositories_completeness": "unavailable"}
    try:
        q = urlencode({"q": f"author:{username} is:pr is:merged is:public", "per_page": 5})
        data = client.get("search/issues?" + q)
        count = data.get("total_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise APIError("Missing or invalid PR search count")
        report["authored_merged_prs"] = {
            "count": count,
            "completeness": "partial" if data.get("incomplete_results", True) else "complete_for_search_scope",
            "query": f"author:{username} is:pr is:merged is:public",
            "url": "https://github.com/search?" + urlencode({"q": f"author:{username} is:pr is:merged is:public", "type": "pullrequests"}),
        }
    except APIError as exc:
        report["warnings"].append(str(exc))
    seen = set()
    try:
        for page in range(1, 11):
            data = client.get(f"users/{username}/repos?type=owner&per_page=100&page={page}")
            if not isinstance(data, list):
                raise APIError("Unexpected repository response")
            for r in data:
                if r.get("private", True) or r.get("owner", {}).get("login", "").lower() != username.lower():
                    continue
                if r.get("fork", True) or r.get("id") in seen:
                    continue
                full_name = r.get("full_name", "")
                try:
                    repository(full_name)
                except ValueError:
                    continue
                seen.add(r.get("id"))
                stars = r.get("stargazers_count")
                if isinstance(stars, bool) or not isinstance(stars, int) or stars < 0:
                    stars = None
                report["repositories"].append({
                    "name": full_name, "stars": stars,
                    "url": safe_url(r.get("html_url", "")), "archived": bool(r.get("archived")),
                    "visibility": "public", "creator_verified": False,
                })
            report["repositories_completeness"] = "partial"
            if len(data) < 100:
                report["repositories_completeness"] = "complete_for_endpoint_scope"
                break
        else:
            report["warnings"].append("Repository pagination limit reached")
    except APIError as exc:
        report["warnings"].append(str(exc))
    report["repositories"].sort(key=lambda r: (-(r["stars"] if r["stars"] is not None else -1), r["name"]))
    return report


def discover(client, repos, limit=5):
    if not 1 <= limit <= 20 or not 1 <= len(repos) <= 5:
        raise ValueError("Use 1–5 repositories and a result limit of 1–20")
    out = {"schema_version": 1, "kind": "opportunities", "scope": "public",
           "observed_at": now(), "opportunities": [], "warnings": [], "repositories_scanned": []}
    seen = set()
    for repo in dict.fromkeys(repos):
        repository(repo)
        if repo.lower() == "community/community":
            out["warnings"].append("Excluded community/community: achievements disabled there")
            continue
        try:
            metadata = client.get("repos/" + repo)
            if metadata.get("private", True) or metadata.get("archived", True):
                out["warnings"].append("A selected repository was excluded (private or archived)")
                continue
            out["repositories_scanned"].append(repo)
            q = urlencode({"q": f'repo:{repo} is:issue is:open no:assignee label:"good first issue"',
                           "sort": "updated", "order": "desc", "per_page": 10})
            data = client.get("search/issues?" + q)
            if data.get("incomplete_results"):
                out["warnings"].append(f"Issue search for {repo} was incomplete")
            for item in data.get("items", []):
                if item.get("state") != "open" or item.get("pull_request") or item.get("assignees") or item.get("locked"):
                    continue
                url = safe_url(item.get("html_url", ""))
                if not url or not url.lower().startswith(f"https://github.com/{repo.lower()}/issues/"):
                    continue
                title = item.get("title", "Untitled")
                docs = any(word in title.lower() for word in ("doc", "example", "readme"))
                if url not in seen:
                    seen.add(url)
                    out["opportunities"].append({"kind": "issue", "title": title, "url": url,
                        "repo": repo, "visibility": "public", "minutes_estimate": 45 if docs else 90,
                        "score": 3 if docs else 2, "achievement": "pull-shark", "created_at": item.get("created_at", ""),
                        "reason": "Open, unassigned, maintainer-labelled good first issue. Check comments and linked PRs before starting."})
        except APIError as exc:
            out["warnings"].append(str(exc))
            continue
        if not metadata.get("has_discussions"):
            continue
        try:
            data = client.discussions(repo)
            if data.get("isPrivate", True) or data.get("isArchived", True):
                continue
            for item in data.get("discussions", {}).get("nodes", []):
                if item.get("closed") or item.get("locked") or item.get("answer"):
                    continue
                if not (item.get("category") or {}).get("isAnswerable"):
                    continue
                url = safe_url(item.get("url", ""))
                if not url or not url.lower().startswith(f"https://github.com/{repo.lower()}/discussions/") or url in seen:
                    continue
                seen.add(url)
                out["opportunities"].append({"kind": "discussion", "title": item.get("title", "Untitled"),
                    "url": url, "repo": repo, "visibility": "public", "minutes_estimate": 30,
                    "score": 3, "achievement": "galaxy-brain", "created_at": item.get("createdAt", ""),
                    "reason": "Unanswered question in an answerable category. Read context and verify a solution; acceptance is up to the community."})
        except APIError as exc:
            out["warnings"].append(str(exc))
    # Stable sorts keep recent questions ahead of old threads with a new comment.
    out["opportunities"].sort(key=lambda x: x["url"])
    out["opportunities"].sort(key=lambda x: x["created_at"], reverse=True)
    out["opportunities"].sort(key=lambda x: (-x["score"], x["minutes_estimate"]))
    out["opportunities"] = out["opportunities"][:limit]
    out["coverage_note"] = "Bounded sample: up to 10 labelled issues and 20 recent discussions per repository, not exhaustive. Estimates are rough effort estimates, not success probabilities."
    return out


def plan(report, minutes=45):
    if not 1 <= minutes <= 480:
        raise ValueError("Minutes must be between 1 and 480")
    if report.get("kind") != "opportunities" or report.get("scope") != "public":
        raise ValueError("Planning requires a public opportunity report")
    result = copy.deepcopy(report)
    result["kind"] = "plan"
    result["minutes_available"] = minutes
    result["opportunities"] = [x for x in result.get("opportunities", [])
                               if x.get("visibility") == "public" and 0 < x.get("minutes_estimate", 999) <= minutes][:3]
    if not result["opportunities"]:
        result["warnings"].append("No observed opportunity fits this time budget. Do not create an artificial task to fill it.")
    return result


def md(value):
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value))
    return re.sub(r"([\\`*_{}\[\]()#+.!|<>~])", r"\\\1", text)


def public_report(data):
    """Project an imported report onto the public schema before either export format."""
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("scope") != "public":
        raise ValueError("Only schema v1 public reports can be exported")
    if data.get("kind") not in ("audit", "opportunities", "plan"):
        raise ValueError("Unsupported report kind")
    keys = ("schema_version", "kind", "scope", "username", "observed_at", "rules_source",
            "rules_verified_on", "repositories_completeness", "coverage_note", "minutes_available")
    result = {key: data[key] for key in keys if key in data}
    result["warnings"] = [x for x in data.get("warnings", []) if isinstance(x, str)]
    result["achievements"] = [{k: item[k] for k in ("slug", "status", "observed_on") if k in item}
                              for item in data.get("achievements", []) if item.get("slug") in RULES]
    p = data.get("authored_merged_prs", {})
    if p:
        result["authored_merged_prs"] = {k: p[k] for k in ("count", "completeness", "query", "url") if k in p}
    for group, fields in (("repositories", ("name", "stars", "url", "archived", "visibility", "creator_verified")),
                          ("opportunities", ("kind", "title", "url", "repo", "visibility", "minutes_estimate", "score", "achievement", "reason", "created_at"))):
        result[group] = [{k: item[k] for k in fields if k in item}
                         for item in data.get(group, [])
                         if item.get("visibility") == "public" and safe_url(item.get("url", ""))]
    result["repositories_scanned"] = [x for x in data.get("repositories_scanned", []) if isinstance(x, str)]
    return result


def render(report):
    report = public_report(report)
    if report.get("schema_version") != 1 or report.get("scope") != "public":
        raise ValueError("Only schema v1 public reports can be exported")
    lines = ["# GitHub contribution report", "", f"Observed: {md(report.get('observed_at', 'unknown'))}", "",
             "Public evidence only. Activity counts are not GitHub's official achievement counters.", ""]
    if report.get("kind") == "audit":
        lines += [f"User: {md(report.get('username', 'unknown'))}", "", "## Confirmed profile observations", ""]
        badges = report.get("achievements", [])
        if not badges:
            lines.append("No profile observations supplied. API activity cannot establish whether a badge was awarded.")
        for badge in badges:
            if badge.get("slug") in RULES:
                lines.append(f"- {RULES[badge['slug']]['name']}: {md(badge.get('status'))} (confirmed {md(badge.get('observed_on'))})")
        p = report.get("authored_merged_prs", {})
        count = "Unknown" if p.get("count") is None else p["count"]
        lines += ["", "## Contribution evidence", "", f"Authored merged PRs observed in public search: **{md(count)}** ({md(p.get('completeness'))}).", "",
                  "Stars are counted per owned, non-fork public repository. Ownership does not prove original creation.", "",
                  "| Repository | Stars | Reference target |", "| --- | ---: | ---: |"]
        for r in report.get("repositories", []):
            if r.get("visibility") != "public":
                continue
            url = safe_url(r.get("url", ""))
            if url:
                stars = "Unknown" if r.get("stars") is None else r["stars"]
                lines.append(f"| [{md(r['name'])}]({url}) | {md(stars)} | 16 |")
        lines += ["", f"Repository coverage: {md(report.get('repositories_completeness'))}.", "",
                  f"Thresholds are [community observations]({RULE_SOURCE}); actual awards and upgrades must be checked on GitHub.", "",
                  "Galaxy Brain accepted-answer totals and Pair Extraordinaire coauthor totals are not measured by this version."]
    elif report.get("kind") in ("opportunities", "plan"):
        lines += ["## Next contribution opportunities", ""]
        entries = [x for x in report.get("opportunities", []) if x.get("visibility") == "public" and safe_url(x.get("url", ""))]
        if not entries:
            lines.append("No matching opportunities observed in this sample.")
        for item in entries:
            lines += [f"- [{md(item['title'])}]({safe_url(item['url'])}) — about {md(item['minutes_estimate'])} minutes; {md(item['kind'])}.",
                      f"  {md(item['reason'])}"]
        lines += ["", md(report.get("coverage_note", "Bounded sample, not exhaustive."))]
    else:
        raise ValueError("Unsupported report kind")
    if report.get("warnings"):
        lines += ["", "## Data limitations", ""]
        # Only tool-generated warnings are expected. Reports should not contain private observations.
        lines.extend("- " + md(x) for x in report["warnings"])
    return "\n".join(lines) + "\n"
