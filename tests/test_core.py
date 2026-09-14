import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from gh_pro.cli import main
from gh_pro.client import APIError, Client, login, repository
from gh_pro.core import audit, discover, plan, public_report, render, safe_url


def repo(name="tester/project", stars=5, **kwargs):
    return dict(id=name, full_name=name, owner={"login": name.split("/")[0]},
                private=False, fork=False, archived=False, stargazers_count=stars,
                html_url="https://github.com/" + name, **kwargs)


class FakeClient:
    def __init__(self, responses, discussions=None):
        self.responses = iter(responses)
        self.discussion_data = discussions
        self.calls = []

    def get(self, endpoint):
        self.calls.append(endpoint)
        data = next(self.responses)
        if isinstance(data, Exception):
            raise data
        return copy.deepcopy(data)

    def discussions(self, name):
        if isinstance(self.discussion_data, Exception):
            raise self.discussion_data
        return copy.deepcopy(self.discussion_data)


class AuditTests(unittest.TestCase):
    def test_missing_star_count_is_unknown(self):
        r = repo(); del r["stargazers_count"]
        data = audit(FakeClient([{"total_count": 2}, [r]]), "tester")
        self.assertIsNone(data["repositories"][0]["stars"])
        self.assertIn("| Unknown | 16 |", render(data))

    def test_failure_is_unknown_not_zero(self):
        result = audit(FakeClient([APIError("offline"), APIError("offline")]), "tester")
        self.assertIsNone(result["authored_merged_prs"]["count"])
        self.assertEqual(result["repositories_completeness"], "unavailable")
        self.assertIn("Unknown", render(result))

    def test_api_counts_never_grant_achievements(self):
        result = audit(FakeClient([{"total_count": 1024, "incomplete_results": False}, []]), "tester")
        self.assertEqual(result["achievements"], [])
        self.assertIn("cannot establish", render(result))

    def test_private_forks_foreign_owners_and_duplicate_ids_excluded(self):
        public = repo()
        private = repo("tester/secret"); private["private"] = True
        fork = repo("tester/fork"); fork["fork"] = True
        result = audit(FakeClient([{"total_count": 1, "incomplete_results": True},
                                  [public, private, fork, repo("someone/other"), public]]), "tester")
        self.assertEqual(len(result["repositories"]), 1)
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(result["authored_merged_prs"]["completeness"], "partial")

    def test_pagination_and_single_repo_stars(self):
        page = [repo("tester/p" + str(i), 1) for i in range(100)]
        client = FakeClient([{"total_count": 2, "incomplete_results": False}, page, [repo(stars=9)]])
        result = audit(client, "tester")
        self.assertIn("page=2", client.calls[-1])
        self.assertEqual(result["repositories"][0]["stars"], 9)
        self.assertEqual(len(result["repositories"]), 101)
        self.assertEqual(result["repositories_completeness"], "complete_for_endpoint_scope")

    def test_partial_pagination_keeps_successful_evidence(self):
        page = [repo("tester/p" + str(i)) for i in range(100)]
        result = audit(FakeClient([{"total_count": 2}, page, APIError("limit")]), "tester")
        self.assertEqual(len(result["repositories"]), 100)
        self.assertEqual(result["repositories_completeness"], "partial")

    def test_wrong_baseline_rejected_without_network(self):
        with self.assertRaises(ValueError):
            audit(FakeClient([]), "tester", {"username": "someone"})

    def test_baseline_only_imports_known_achievement_fields(self):
        b = {"username": "tester", "observed_on": "2026-09-15", "private_token": "secret",
             "activity_observations": [{"private": True}], "achievements": [{"slug": "yolo", "status": "earned", "private": "secret"}]}
        r = audit(FakeClient([{"total_count": 2}, []]), "tester", b)
        self.assertEqual(r["achievements"][0]["status"], "earned")
        self.assertNotIn("secret", json.dumps(r))


class OpportunityTests(unittest.TestCase):
    def test_recent_questions_rank_ahead_of_old_threads(self):
        base = {"title": "Question", "closed": False, "locked": False, "answer": None, "category": {"isAnswerable": True}}
        items = [dict(base, url="https://github.com/tester/project/discussions/1", createdAt="2021-01-01T00:00:00Z"),
                 dict(base, url="https://github.com/tester/project/discussions/9", createdAt="2026-09-14T00:00:00Z")]
        c = FakeClient([repo(has_discussions=True), {"items": []}], {"isPrivate": False, "isArchived": False, "discussions": {"nodes": items}})
        self.assertTrue(discover(c, ["tester/project"])["opportunities"][0]["url"].endswith("/9"))

    def test_community_is_not_queried(self):
        client = FakeClient([])
        data = discover(client, ["community/community"])
        self.assertEqual(client.calls, [])
        self.assertFalse(data["opportunities"])

    def test_private_repo_never_queried_for_content(self):
        client = FakeClient([{"private": True, "archived": False}])
        result = discover(client, ["tester/secret"])
        self.assertEqual(len(client.calls), 1)
        self.assertNotIn("secret", json.dumps(result))

    def test_discussion_category_answer_closed_and_url_filters(self):
        base = {"title": "Question", "url": "https://github.com/tester/project/discussions/1",
                "closed": False, "locked": False, "answer": None, "category": {"isAnswerable": True}}
        items = [base, dict(base, answer={"id": "answer"}), dict(base, closed=True),
                 dict(base, category={"isAnswerable": False}), dict(base, locked=True),
                 dict(base, url="https://evil.example/test"), base]
        client = FakeClient([repo(has_discussions=True), {"items": []}],
                            {"isPrivate": False, "isArchived": False, "discussions": {"nodes": items}})
        result = discover(client, ["tester/project"])
        self.assertEqual(len(result["opportunities"]), 1)
        self.assertEqual(result["opportunities"][0]["achievement"], "galaxy-brain")

    def test_issue_and_pr_and_assignment_filters(self):
        base = {"title": "Improve docs", "html_url": "https://github.com/tester/project/issues/1",
                "state": "open", "assignees": [], "locked": False}
        items = [base, dict(base, pull_request={"url": "pr"}), dict(base, assignees=[{"login": "a"}]),
                 dict(base, state="closed"), dict(base, html_url="https://github.com/other/repo/issues/1")]
        result = discover(FakeClient([repo(), {"items": items}]), ["tester/project"])
        self.assertEqual(len(result["opportunities"]), 1)
        self.assertEqual(plan(result, 45)["opportunities"][0]["minutes_estimate"], 45)
        self.assertFalse(plan(result, 10)["opportunities"])

    def test_partial_graphql_does_not_count(self):
        client = FakeClient([repo(has_discussions=True), {"items": []}], APIError("GraphQL failure"))
        self.assertEqual(discover(client, ["tester/project"])["opportunities"], [])


class SafetyTests(unittest.TestCase):
    def test_json_projection_discards_private_and_extra_fields(self):
        r = {"schema_version": 1, "kind": "audit", "scope": "public", "token": "secret",
             "repositories": [{"name": "secret", "url": "https://github.com/a/private", "visibility": "private"},
                              {"name": "a/public", "url": "https://github.com/a/public", "visibility": "public", "extra": "secret"}]}
        output = json.dumps(public_report(r))
        self.assertNotIn("secret", output)
        self.assertNotIn("extra", output)

    def test_input_cannot_be_shell_or_path(self):
        for name in ("a/b", "$(whoami)", "--help", "test\nother"):
            with self.assertRaises(ValueError):
                login(name)
        for name in ("a/../b", "a/..", "a/repo?token=x", "a/repo;ls"):
            with self.assertRaises(ValueError):
                repository(name)

    def test_untrusted_links_not_rendered(self):
        for url in ("javascript:alert(1)", "https://github.com.evil.example/a", "https://github.com@evil.example/a", "https://github.com/a\n<script>"):
            self.assertEqual(safe_url(url), "")

    def test_markdown_injection_escaped(self):
        d = {"schema_version": 1, "kind": "opportunities", "scope": "public", "warnings": [], "opportunities": [
            {"title": "x](https://evil.example) <img>", "url": "https://github.com/a/b/issues/1", "visibility": "public",
             "minutes_estimate": 30, "kind": "issue", "reason": "<script>alert(1)</script>"}]}
        output = render(d)
        self.assertNotIn("[x](https://evil.example)", output)
        self.assertNotIn("<script>", output)

    def test_nonpublic_report_rejected(self):
        with self.assertRaises(ValueError):
            render({"schema_version": 1, "scope": "private"})

    def test_request_budget(self):
        with self.assertRaises(APIError):
            Client(max_requests=0).get("users/tester/repos")

    def test_cli_demo_is_offline(self):
        with patch("gh_pro.client.Client.get", side_effect=AssertionError("network")):
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(["demo"]), 0)
            self.assertIn("Synthetic offline example", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
