# Contributing

Small, complete improvements are welcome: a clearer error message, a reproducible filtering bug, a documented API edge case, or better report output.

1. Check existing issues and pull requests for related work.
2. Make the smallest complete change that solves the problem.
3. Add a test when behavior or a failure case changes. Use synthetic fixtures; never commit personal reports, tokens, or private repository data.
4. Run `python3 -m unittest discover -s tests -v` and `python3 -m gh_pro demo`.
5. Explain the trigger, resulting behavior, and validation in your PR.

Report a bug with the command, Python version, expected result, and sanitized output. Include public repository URLs only when needed to reproduce it. Do not paste credentials or raw private API responses.

This project is read-only by design. Suggestions that require posting, merging, accepting answers, or modifying account settings need a separate design discussion. No artificial issue/PR generation, fabricated coauthors, or reciprocal-star schemes.

For joint work, credit only actual contributors with their agreed GitHub-associated email or no-reply address. See [GitHub's coauthor documentation](https://docs.github.com/en/pull-requests/how-tos/commit-changes/creating-a-commit-with-multiple-authors).
