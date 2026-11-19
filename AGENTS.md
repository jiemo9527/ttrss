# Contributor rules

- Preserve upstream history/licenses. `origin` is jiemo9527/ttrss, `upstream` is HenryQW/Awesome-TTRSS.
- Scope: Docker packaging, bridge, refresh options, upstream/security maintenance. Do not confuse with the separate Telegram forwarder `t2rss`.
- Secrets, bridge.key, .env, production compose, database and runtime content must never be committed or logged.
- Keep shell/PHP/YAML LF. New behavior gets regression tests; upstream layout changes must fail loudly instead of silently dropping patches.
- `php tests/maintenance.php`, `python tests/sync-upstream-test.py`; lint PHP and shell; CI builds the image, runs the feed e2e test, verifies the nginx baseline (`scripts/check-nginx-version.sh`) and bridge fail-closed behavior, then publishes amd64/arm64.
- Upstream sync is automated by `scripts/sync-upstream.py` + `.github/workflows/upstream.yml`: candidates must pass all tests before fast-forwarding `main`; conflicts open an issue. Never deploy production from CI. Keep fork-owned paths (README, compose, workflows) excluded from upstream patches; plugin/theme downloads remain floating.
- Production data migration is a separate explicitly scoped step: inspect existing entrypoint/bridge mounts, snapshot DB, run candidate on isolated DB, then deploy with rollback. Never publish data snapshots.
- Bridge authentication must remain constant-time and fail closed; no error-body leaks. Preserve existing key-query compatibility while recommending header auth. FlareSolverr needs separate network/SSRF isolation.
