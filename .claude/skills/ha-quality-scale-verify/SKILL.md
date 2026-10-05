---
name: ha-quality-scale-verify
description: Verifies that a Home Assistant integration follows a specific quality scale rule, checking whether it implements the required patterns, configurations, or code structures defined by the quality scale system. Use when asked to check a rule (e.g. "check if the peblar integration follows the config-flow rule") or to verify an integration reaches a quality tier (Bronze, Silver, Gold, Platinum).
---

# Verify Quality Scale Rule

You are verifying whether a Home Assistant integration follows a specific quality scale rule. Verify one rule at a time; to check a full tier, verify each of that tier's rules (run in parallel subagents when possible).

Reading the code is not enough. Many rules have an objective threshold or a validator that Home Assistant's own CI enforces. For those you MUST run the tool and read its result, not infer the outcome from the source. A rule with no finding is only "pass" if you actually checked it — never report a pass you did not verify. When a rule is measurable or tool-enforced, report the measured number or the tool's verdict; when it is a judgment from reading code, say so; when you could not check it, mark it "unverified" rather than implying it passed.

## 1. Fetch rule documentation
Retrieve the official rule documentation from:
`https://raw.githubusercontent.com/home-assistant/developers.home-assistant/refs/heads/master/docs/core/integration-quality-scale/rules/{rule_name}.md`
where `{rule_name}` is the rule identifier (e.g. `config-flow`, `entity-unique-id`, `parallel-updates`). Read the exact wording of the requirement — the threshold matters (e.g. test-coverage is "Above 95% test coverage for all integration modules", i.e. per module, not an aggregate).

## 2. Understand rule requirements
Parse the rule documentation to identify:
- Core requirements and mandatory implementations
- Specific code patterns or configurations required
- Common violations and anti-patterns
- Exemption criteria (when a rule might not apply)
- The quality tier this rule belongs to (Bronze, Silver, Gold, Platinum)

## 3. Check against the PR head
Verify the code as it is in the change under review, not the base branch. If verifying a PR, check out its head (e.g. `git fetch origin pull/<n>/head:pr/<n> && git checkout pr/<n>`) so `manifest.json`, `quality_scale.yaml`, the modules and the tests are the ones being proposed.

Examine `homeassistant/components/<domain>`:
- `manifest.json` for the declared `quality_scale` tier and configuration
- `quality_scale.yaml` for each rule's status (`done`, `todo`, `exempt`)
- the Python modules and `tests/components/<domain>` relevant to the rule

Additional sources:
- Integration docs: resolve in this order — the docs change in the PR, then its linked docs PR, then the `next` branch, then the `current` branch of home-assistant.io (`https://raw.githubusercontent.com/home-assistant/home-assistant.io/refs/heads/<branch>/source/_integrations/<domain>.markdown`). Docs for a tier bump usually land on `next` or in a docs PR, so `current` alone is often stale. If you could read these sources and the required `docs-*` section is absent from all of them, that is **verified non-compliance — report it as a finding**. Mark a `docs-*` rule **unverified** only when you could not reach the docs (no linked docs PR and the source could not be fetched), and say what is needed.
- PyPI package info: `https://pypi.org/pypi/<package>/json`

## 3b. Determine which rules to verify
- **If the change modifies the integration's `quality_scale` tier** (a tier bump — the `quality_scale` value in `manifest.json` changes), verify **every rule from Bronze up to and including the target tier**, from scratch. Do not trust the existing `done`/`exempt` marks or assume prior reviewers verified the lower tiers — re-run the checks and re-read the code for all of them. A tier bump is exactly where a lower-tier rule that was wrongly marked `done` (a docs section that was never written, a coverage gap) slips through, so the whole cumulative set is in scope.
- **If the change flips rules but not the tier** (e.g. it sets some rules to `done`, or adds an initial scorecard), verify every rule whose `quality_scale.yaml` status this change **changes in any direction** (diff `quality_scale.yaml`) — not only flips to `done`/`exempt`. A revert to `todo` matters too: if the reverted rule is at or below the integration's declared tier, the tier claim is no longer met (hassfest errors on this — `script/hassfest/quality_scale.py`), so report it as a tier regression. `todo` rules above the declared tier (or on an integration with no tier) are acknowledged gaps, not findings.
- **If the change touches code but changes no `quality_scale.yaml` rule and no manifest level** (an ordinary code PR), verify by default that the changed code still complies with the rules that apply at the integration's **current** `quality_scale` tier (all rules from Bronze up to that tier are in force). Map the diff to the rules it implicates and check those — don't re-verify the whole tier. For example: a touched `config_flow.py` implicates `config-flow`, `config-flow-test-coverage`, `reauthentication-flow`, `reconfiguration-flow`; a new or changed entity implicates `entity-unique-id`, `has-entity-name`, `entity-category`, `entity-device-class`, `entity-translations`, `icon-translations`; new/changed actions implicate `action-setup`, `action-exceptions`, `docs-actions`; changed modules implicate `test-coverage` (re-measure coverage on those modules). Run the executable checks (hassfest, mypy, `pytest --cov`) for the implicated rules. The bar is no regression: a code change must not drop the integration below the tier it already holds.
- When only a single rule was requested, verify just that rule.

## 4. Run the checks (mandatory for executable rules)

Set up the dev environment once (see the repo `AGENTS.md`): run `script/setup`. If uv reports no download for the required Python, upgrade uv first (`pip install -U uv` from PyPI, since `astral.sh` may be blocked) and re-run `script/setup`.

`script/setup` activates `.venv` only inside its own subprocess, so that activation does not carry over to your shell. Run every check below through `uv run --no-sync <tool>` (or `source .venv/bin/activate` first); a bare `python`/`pytest`/`mypy` can hit the system interpreter and give untrustworthy results.

Match the PR's pinned versions before linting or testing — version drift and missing packages produce both false failures and false passes. Read the pins from the PR head and install them:
- `ruff` pin from `requirements_test_pre_commit.txt` (and `.pre-commit-config.yaml`); install it (`uv pip install "ruff==<pin>"`). hassfest calls `ruff format`, so install this before hassfest too.
- `syrupy` pin from `requirements_test.txt`; install it before running snapshot tests.
- the integration's own libraries from `manifest.json` `requirements` (`uv pip install "<pkg>==<pin>"`). A stale or missing library makes mypy and hassfest report errors that are not in the code. If an import fails (`ModuleNotFoundError`) or mypy flags library symbols, install the correct version and re-run — that is a build-environment gap, not a PR defect. Do not report a missing/mismatched dependency as a rule violation, and do not assume an unfamiliar imported package is a mistake: confirm it is really absent from the project's requirements before treating an import as broken.

Map each rule to the check that actually proves it:

- **hassfest** — the coded validators. Run `uv run --no-sync python -m script.hassfest --integration-path homeassistant/components/<domain>` (exit 0, "Invalid integrations: 0"). This validates `quality_scale.yaml` structure/completeness and the rules with built-in validators: `config-flow`, `runtime-data`, `test-before-setup`, `unique-config-entry`, `discovery`, `reconfiguration-flow`, and the `strict-typing` manifest wiring. hassfest invokes `ruff format` internally, so the pinned ruff must be installed or it fails spuriously. Note `--integration-path` runs only the per-integration plugins, not the full-repo ones (`script/hassfest/__main__.py`), so it does not run `mypy_config` or validate brand assets (see below). A rule's validator runs **only when that rule is marked `done`** (`script/hassfest/quality_scale.py`): hassfest iterates the `done` rules and skips `todo`/`exempt` ones. So a clean hassfest proves a validator-backed rule only if it is `done`; when you are verifying a rule that is `todo`/`exempt` (a code-PR implicated rule, or judging whether a `todo` could become `done`), run that rule's check directly or mark it **unverified** — do not read exit 0 as proof its validator ran.
- **strict-typing** (platinum) — run `uv run --no-sync mypy homeassistant/components/<domain>`. mypy reads its settings from `mypy.ini`, which hassfest's `mypy_config` plugin generates from `.strict-typing` — and the integration-scoped hassfest above does **not** run that plugin. So adding the integration to `.strict-typing` without regenerating `mypy.ini` leaves strict off and mypy passes under non-strict settings. First confirm the integration is actually listed in `.strict-typing` — membership is necessary for the claim, and if it is absent (and neither file changed) mypy runs non-strict and passes vacuously. Then confirm `mypy.ini` is in sync with `.strict-typing` by running the plugin in **validate** mode: `uv run --no-sync python -m script.hassfest -p mypy_config --action validate`. Never omit `--action validate` here — without it hassfest defaults to `generate` (`__main__.py`), which silently rewrites `mypy.ini` in the checkout and masks the very staleness you are checking for; a check that passes only after regeneration is not verification of the PR head. If validate reports the config is out of date, that is a finding (the PR did not regenerate `mypy.ini`, so strict typing is not actually enforced). Membership and `py.typed` are necessary but not sufficient — mypy must also pass.
- **test-coverage** (silver+) — before running, regenerate translations: `uv run --no-sync python -m script.translations develop --integration <domain>` (tests load `translations/en.json`, a build artifact, not `strings.json`). Then run `uv run --no-sync pytest tests/components/<domain> --cov=homeassistant.components.<domain> --cov-report=term-missing`. The rule is **above 95% per module** (strictly greater), so exactly 95% fails (19/20 statements = 95.0%). Report every module **not above 95% (i.e. ≤95%)** using exact covered/total counts, not the rounded percentage (a displayed "95%" from 36/38 is 94.7%), with its missing lines.
- **config-flow-test-coverage** (bronze) — from the same coverage run, `config_flow.py` must be fully covered (100%), and the rule's scenarios must be tested across every flow the integration supports. The rule explicitly covers the user and discovery setup flows, reconfigure, reauthentication, and the **options flow**. Each flow must reach its appropriate successful terminal result after recovering from errors: `CREATE_ENTRY` for user/discovery/import setup and for an options flow that writes options; `ABORT` with `reauth_successful` / `reconfigure_successful` for reauth / reconfigure (these succeed with ABORT, not CREATE_ENTRY). The duplicate/`already_configured` abort path must also be exercised. The options flow lives in `config_flow.py` (returned by `async_get_options_flow`), so it is already inside the 100% `config_flow.py` requirement — cover it there; no need to look outside that file. 100% line coverage without these scenarios still fails.
- **docs-*** — check the required sections exist in the integration docs, resolving the source as described in §3 (PR docs → linked docs PR → `next` → `current`). A required section absent from readable sources is a finding; mark the rule unverified only when the docs could not be reached.
- **brands** (bronze) — not proven by hassfest: `brands` has no quality-scale validator (`script/hassfest/quality_scale.py`), and brand assets live in the separate `home-assistant/brands` repo. Verify the required assets there or in the linked brands PR; if you cannot reach them, mark the rule **unverified**, not pass.
- All other rules (`has-entity-name`, `appropriate-polling`, `parallel-updates`, `entity-category`, exemptions, etc.) — verify by reading the code against the rule doc; confirm with hassfest where it applies.

Quality scale rules are cumulative: Bronze rules apply to every integration with a quality scale, Silver rules to Silver+ , and so on. Enforce a rule only at or above the tier it belongs to (e.g. `test-coverage` is Silver — do not fail a Bronze claim on it). A rule left `todo` at or below the claimed tier means the claim is unjustified. A rule marked `done` that the check fails is a finding. An `exempt` reason that describes an implementation gap rather than genuine non-applicability is a finding (some rules state they have no exceptions).

## 5. Report findings
Report only the rules that have issues. Do not list rules that pass or that are validly exempt. For each rule with an issue, provide:
- **Rule**: the rule identifier and the problem (non-compliance, an over-claimed `done`, or an invalid/unjustified `exempt`)
- **Evidence**: the measured result or tool output, and specific file locations (e.g. `select.py` at 94%, missing lines; hassfest/mypy error; the `quality_scale.yaml` line)
- **Recommendation**: actionable steps to achieve compliance

State which checks you actually ran. If a check could not be run (environment, cross-repo `brands`, docs not yet merged), mark that rule "unverified" and say what is needed — never let an unrun check read as a pass. If no rules have issues, say so in a single line.
