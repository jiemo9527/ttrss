# Contributor rules

- Preserve upstream history/licenses. `origin` is jiemo9527/ttrss, `upstream` is HenryQW/Awesome-TTRSS.
- Scope: Docker packaging, bridge, refresh options, upstream/security maintenance. Do not confuse with the separate Telegram forwarder `t2rss`.
- Secrets, bridge.key, .env, production compose, database and runtime content must never be committed or logged.
- Keep shell/PHP/YAML LF. New behavior gets regression tests; upstream layout changes must fail loudly instead of silently dropping patches.
- `php tests/maintenance.php`; lint PHP and shell; CI builds amd64/arm64, verifies nginx baseline and bridge fail-closed behavior.
- Never auto-merge upstream or deploy production from scheduled builds. Pin application commits; document remaining floating plugin/theme inputs.
- Production data migration is a separate explicitly scoped step: inspect existing entrypoint/bridge mounts, snapshot DB, run candidate on isolated DB, then deploy with rollback. Never publish data snapshots.
- Bridge authentication must remain constant-time and fail closed; no error-body leaks. Preserve existing key-query compatibility while recommending header auth. FlareSolverr needs separate network/SSRF isolation.
