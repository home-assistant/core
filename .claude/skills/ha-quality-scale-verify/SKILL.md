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
- Integration docs: resolve in this order — the docs change in the PR, then its linked docs PR, then the `next` branch, then the `current` branch of home-assistant.io (`https://raw.githubusercontent.com/home-assistant/home-assistant.io/refs/heads/<branch>/source/_integrations/<domain>.markdown`). Docs for a tier bump usually land on `next` or in a docs PR, so `current` alone is often stale. If a required `docs-*` section is not found in any of these, mark that rule **unverified — needs the docs PR linked**, not pass and not a hard fail.
- PyPI package info: `https://pypi.org/pypi/<package>/json`

## 3b. Determine which rules to verify
- **If the change modifies the integration's `quality_scale` tier** (a tier bump — the `quality_scale` value in `manifest.json` changes), verify **every rule from Bronze up to and including the target tier**, from scratch. Do not trust the existing `done`/`exempt` marks or assume prior reviewers verified the lower tiers — re-run the checks and re-read the code for all of them. A tier bump is exactly where a lower-tier rule that was wrongly marked `done` (a docs section that was never written, a coverage gap) slips through, so the whole cumulative set is in scope.
- **If the change does not move the tier** (e.g. it flips some rules to `done`, or adds an initial scorecard), verify every rule whose `quality_scale.yaml` status this change adds or sets to `done`/`exempt` (diff `quality_scale.yaml`), plus any rule the code changes touch. `todo` rules at or below the claimed tier are acknowledged gaps, not findings — but they mean a full tier claim is not yet met.
- When only a single rule was requested, verify just that rule.

## 4. Run the checks (mandatory for executable rules)

Set up the dev environment once (see the repo `CLAUDE.md`): run `script/setup`. If uv reports no download for the required Python, upgrade uv first (`pip install -U uv` from PyPI, since `astral.sh` may be blocked) and re-run `script/setup`.

Match the PR's pinned versions before linting or testing — version drift and missing packages produce both false failures and false passes. Read the pins from the PR head and install them:
- `ruff` pin from `requirements_test_pre_commit.txt` (and `.pre-commit-config.yaml`); install it (`uv pip install "ruff==<pin>"`). hassfest calls `ruff format`, so install this before hassfest too.
- `syrupy` pin from `requirements_test.txt`; install it before running snapshot tests.
- the integration's own libraries from `manifest.json` `requirements` (`uv pip install "<pkg>==<pin>"`). A stale or missing library makes mypy and hassfest report errors that are not in the code. If an import fails (`ModuleNotFoundError`) or mypy flags library symbols, install the correct version and re-run — that is a build-environment gap, not a PR defect. Do not report a missing/mismatched dependency as a rule violation, and do not assume an unfamiliar imported package is a mistake: confirm it is really absent from the project's requirements before treating an import as broken.

Map each rule to the check that actually proves it:

- **hassfest** — the coded validators. Run `python -m script.hassfest --integration-path homeassistant/components/<domain>` (exit 0, "Invalid integrations: 0"). This validates `quality_scale.yaml` structure/completeness and the rules with built-in validators: `config-flow`, `runtime-data`, `test-before-setup`, `unique-config-entry`, `discovery`, `reconfiguration-flow`, `brands`, and the `strict-typing` manifest wiring. hassfest invokes `ruff format` internally, so the pinned ruff must be installed or it fails spuriously.
- **strict-typing** (platinum) — run `mypy homeassistant/components/<domain>`. The strict config is applied automatically to integrations listed in `.strict-typing`. "Success: no issues found" is the pass; do not conclude strict-typing from `.strict-typing` membership or `py.typed` alone.
- **test-coverage** (silver+) — before running, regenerate translations: `python -m script.translations develop --integration <domain>` (tests load `translations/en.json`, a build artifact, not `strings.json`). Then run `pytest tests/components/<domain> --cov=homeassistant.components.<domain> --cov-report=term-missing`. The rule is **per module**: every module must be above 95% (watch rounding — a displayed "95%" from e.g. 36/38 is 94.7% and fails). Report each module below 95% with its missing lines.
- **config-flow-test-coverage** (bronze) — from the same coverage run, `config_flow.py` must be fully covered (100%), and the rule's scenarios must be tested: each error path recovers and the flow still reaches `CREATE_ENTRY`, and the duplicate/`already_configured` abort path is exercised. 100% line coverage without those scenarios still fails.
- **docs-*** — check the required sections exist in the integration docs (from the PR/linked docs PR, or the live markdown as a fallback).
- All other rules (`has-entity-name`, `appropriate-polling`, `parallel-updates`, `entity-category`, exemptions, etc.) — verify by reading the code against the rule doc; confirm with hassfest where it applies.

Quality scale rules are cumulative: Bronze rules apply to every integration with a quality scale, Silver rules to Silver+ , and so on. Enforce a rule only at or above the tier it belongs to (e.g. `test-coverage` is Silver — do not fail a Bronze claim on it). A rule left `todo` at or below the claimed tier means the claim is unjustified. A rule marked `done` that the check fails is a finding. An `exempt` reason that describes an implementation gap rather than genuine non-applicability is a finding (some rules state they have no exceptions).

## 5. Report findings
Report only the rules that have issues. Do not list rules that pass or that are validly exempt. For each rule with an issue, provide:
- **Rule**: the rule identifier and the problem (non-compliance, an over-claimed `done`, or an invalid/unjustified `exempt`)
- **Evidence**: the measured result or tool output, and specific file locations (e.g. `select.py` at 94%, missing lines; hassfest/mypy error; the `quality_scale.yaml` line)
- **Recommendation**: actionable steps to achieve compliance

State which checks you actually ran. If a check could not be run (environment, cross-repo `brands`, docs not yet merged), mark that rule "unverified" and say what is needed — never let an unrun check read as a pass. If no rules have issues, say so in a single line.
