"""Small bounded GitHub client. No mutations, shell interpolation, or token storage."""

import json
import re
import subprocess
import urllib.error
import urllib.request


class APIError(Exception):
    """An unavailable remote observation, never a zero count."""


class RateLimitError(APIError):
    """Stop this run rather than sending more requests after a rate limit."""


RATE_LIMIT_MESSAGE = "GitHub rate limit reached; stopped requests. Retry later."


def rate_limited(data):
    if not isinstance(data, dict):
        return False
    message = str(data.get("message", "")).lower()
    errors = data.get("errors")
    return ("rate limit" in message or "rate-limit" in message or
            (isinstance(errors, list) and any(
                isinstance(error, dict) and error.get("type") == "RATE_LIMITED"
                for error in errors)))


def login(value):
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", value):
        raise ValueError("Invalid GitHub username")
    return value


def repository(value):
    parts = value.split("/")
    if len(parts) != 2:
        raise ValueError("Repository must be OWNER/NAME")
    login(parts[0])
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", parts[1]) or parts[1] in (".", ".."):
        raise ValueError("Invalid repository name")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, auth_gh=False, max_requests=35):
        self.auth_gh = auth_gh
        self.remaining = max_requests

    def _budget(self):
        if self.remaining <= 0:
            raise APIError("Request budget reached; this observation is partial")
        self.remaining -= 1

    def _gh(self, args):
        try:
            result = subprocess.run(
                ["gh", "api", "--hostname", "github.com", *args],
                capture_output=True, text=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise APIError("GitHub CLI unavailable or timed out") from exc
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            if result.returncode:
                raise APIError("GitHub CLI request failed; check authentication or permissions") from exc
            raise APIError("GitHub CLI returned invalid JSON") from exc
        if rate_limited(data):
            raise RateLimitError(RATE_LIMIT_MESSAGE)
        if result.returncode:
            raise APIError("GitHub CLI request failed; check authentication or permissions")
        if isinstance(data, dict) and data.get("errors"):
            raise APIError("GraphQL returned errors; data was not counted")
        return data

    def get(self, endpoint):
        if not endpoint.startswith(("users/", "repos/", "search/")) or "://" in endpoint:
            raise ValueError("Unsupported GitHub API endpoint")
        self._budget()
        if self.auth_gh:
            return self._gh(["--method", "GET", endpoint])
        req = urllib.request.Request(
            "https://api.github.com/" + endpoint,
            headers={"User-Agent": "gh-pro-contributor/0.1", "Accept": "application/vnd.github+json"},
        )
        try:
            with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                data = json.loads(exc.read())
            except (ValueError, OSError):
                data = {}
            if (exc.code == 429 or rate_limited(data) or
                    (exc.code == 403 and (exc.headers.get("Retry-After") is not None or
                                         exc.headers.get("X-RateLimit-Remaining") == "0"))):
                raise RateLimitError(RATE_LIMIT_MESSAGE) from exc
            raise APIError("Public GitHub API request failed (unavailable resource or permission)") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise APIError("Public GitHub API request failed (network, rate limit, or unavailable resource)") from exc

    def discussions(self, repo):
        repository(repo)
        if not self.auth_gh:
            raise APIError("Discussion discovery needs --auth-gh; issue discovery still works without it")
        self._budget()
        owner, name = repo.split("/")
        query = """query($owner:String!,$name:String!) {
          repository(owner:$owner,name:$name) {
            isPrivate isArchived hasDiscussionsEnabled
            discussions(first:20,orderBy:{field:UPDATED_AT,direction:DESC}) {
              nodes { title url createdAt updatedAt closed locked
                category { isAnswerable }
                answer { id }
              }
              pageInfo { hasNextPage }
            }
          }
        }"""
        data = self._gh(["graphql", "-f", "query=" + query, "-f", "owner=" + owner, "-f", "name=" + name])
        result = data.get("data", {}).get("repository")
        if result is None:
            raise APIError("Repository discussions unavailable")
        return result
