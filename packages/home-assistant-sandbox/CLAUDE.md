# Sandbox contributor instructions

- Keep implementation comments focused on constraints and non-obvious decisions.
- Keep README.md current with the architecture, setup, limits, and contribution workflow. Keep research outside this repository; detailed guides can move to contributors.home-assistant.io.
- Merge dev into the shared sandbox branch. Do not rebase or force-push it.
- Keep mirrored wire modules byte-identical; run `bash packages/home-assistant-sandbox/proto/check_mirror_drift.sh` after editing either copy.
- Run Core tests with `uv run --no-sync pytest tests/components/sandbox` from the repository root.
- Run client tests with `uv run --no-sync pytest` from `packages/home-assistant-sandbox`.
- After changing sandbox code, run `uv run --no-sync prek run --files <changed files>` before committing.
- Keep Python manager support and security containment outside v1.
