---
name: ha-quality-scale-verify
description: Verifies that a Home Assistant integration follows a specific quality scale rule, checking whether it implements the required patterns, configurations, or code structures defined by the quality scale system. Use when asked to check a rule (e.g. "check if the peblar integration follows the config-flow rule") or to verify an integration reaches a quality tier (Bronze, Silver, Gold, Platinum).
---

# Verify Quality Scale Rule

You are verifying whether a Home Assistant integration follows a quality scale rule. Verify one rule at a time; to check a full tier, verify each of that tier's rules (parallel subagents when possible).

Reading the code is not enough. Many rules have an objective threshold or a validator that CI enforces — run the tool and read its result instead of inferring from the source. Report the measured number or the tool's verdict; when a rule is a judgment from reading code, say so; when you could not check it, mark it **unverified** rather than implying a pass.

## 1. Understand the rule
Fetch the rule doc from `https://raw.githubusercontent.com/home-assistant/developers.home-assistant/refs/heads/master/docs/core/integration-quality-scale/rules/{rule_name}.md` and read the exact requirement — the wording matters (e.g. test-coverage is "Above 95% test coverage for all integration modules": per module, strictly above 95%). Note the tier the rule belongs to, its required patterns, and its exemption criteria.

## 2. Inspect the integration
Verify the code as it currently is (local working tree, or a checked-out PR head), not the base branch. In `homeassistant/components/<domain>`, read `manifest.json` (declared `quality_scale` tier), `quality_scale.yaml` (each rule's `done`/`todo`/`exempt`), and the modules and `tests/components/<domain>` relevant to the rule.

Other sources: the library on PyPI (`https://pypi.org/pypi/<package>/json`); and the integration docs, resolved in this order — the docs change under review, its linked docs PR, the `next` branch, then the `current` branch of home-assistant.io (`.../home-assistant.io/refs/heads/<branch>/source/_integrations/<domain>.markdown`). Docs for a tier bump usually land on `next` or a docs PR, so `current` alone is often stale.

## 3. Which rules to verify
- **Tier bump** (the `quality_scale` value in `manifest.json` changes): verify every rule from Bronze up to the target tier, from scratch — do not trust the existing `done`/`exempt` marks.
- **Rule status changes, same tier** (flips in `quality_scale.yaml`, or a new scorecard): verify every rule whose status the diff changes, in any direction. A revert to `todo` at or below the declared tier breaks the tier claim.
- **Code change only** (no `quality_scale.yaml` or tier change): verify the changed code still satisfies the rules in force at the integration's current tier. Map the diff to the rules it implicates and check those — the bar is no regression.
- **A single requested rule**: verify just that rule.

## 4. How to prove each rule
Run checks in the project's dev environment. Match the versions the change pins (`ruff` from `requirements_test_pre_commit.txt`, `syrupy` from `requirements_test.txt`, the library from `manifest.json`) — version drift gives false passes and false failures. A missing or stale dependency (ModuleNotFoundError, mypy flagging library symbols) is a build-environment gap to fix, not a rule violation; don't assume an unfamiliar imported package is a mistake without confirming it is absent from the project's requirements.

- **hassfest** (`python -m script.hassfest --integration-path homeassistant/components/<domain>`) — validates `quality_scale.yaml` and the validator-backed rules: `config-flow`, `runtime-data`, `test-before-setup`, `unique-config-entry`, `discovery`, `reconfiguration-flow`, `strict-typing` wiring. Caveats: a rule's validator runs only when that rule is `done`, so a clean run does not prove a `todo`/`exempt` rule — check those directly. The integration-scoped run skips the `mypy_config` and brand-asset validators.
- **strict-typing** (platinum) — run mypy on the integration. It must be listed in `.strict-typing` (else mypy runs non-strict and passes vacuously), and `mypy.ini` must be in sync — validate that (`python3 -m script.hassfest -p mypy_config --action validate`); never let hassfest regenerate it (the default, which hides staleness). `mypy_config` is repo-wide, so scope a failure to the target before reporting it.
- **test-coverage** (silver+) — regenerate translations first (tests load the generated `translations/en.json`, not `strings.json`), then run coverage. The rule is strictly above 95% **per module**; report every module not above 95% by exact covered/total (a rounded "95%" can be 94.7%), with missing lines.
- **config-flow-test-coverage** (bronze) — `config_flow.py` fully covered, and every supported flow tested through error recovery to its correct terminal result: `CREATE_ENTRY` for user/discovery/import setup, `ABORT` + `reauth_successful`/`reconfigure_successful` for reauth/reconfigure, plus the `already_configured` abort. Options flows count and live in `config_flow.py`, so they are already in scope. 100% line coverage without these scenarios still fails.
- **docs-*** — confirm the required sections exist in the docs (resolved as in §2). A section absent from readable sources is a finding; mark unverified only when the docs could not be reached.
- **brands** (bronze) — not proven by hassfest; assets live in `home-assistant/brands`. Verify them there or in the linked brands PR, else mark unverified.
- **Everything else** — verify by reading the code against the rule doc.

Rules are cumulative and enforced at or above their own tier (e.g. `test-coverage` is Silver — it does not fail a Bronze claim). A `done` rule whose check fails is a finding; so is an `exempt` reason that masks an implementation gap rather than genuine non-applicability.

## 5. Report findings
Report only rules with issues. For each: the rule and the problem (non-compliance, over-claimed `done`, or invalid `exempt`), the evidence (measured result / tool output / file location), and the fix. State which checks you ran, and mark anything you could not check as unverified. If nothing has issues, say so in one line.
