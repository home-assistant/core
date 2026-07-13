---
name: ha-quality-scale-verify
description: Verifies that a Home Assistant integration follows a specific quality scale rule, checking whether it implements the required patterns, configurations, or code structures defined by the quality scale system. Use when asked to check a rule (e.g. "check if the peblar integration follows the config-flow rule") or to verify an integration reaches a quality tier (Bronze, Silver, Gold, Platinum).
---

# Verify Quality Scale Rule

You are verifying whether a Home Assistant integration follows a specific quality scale rule. Verify one rule at a time; to check a full tier, verify each of that tier's rules (run in parallel subagents when possible).

## 1. Fetch rule documentation
Retrieve the official rule documentation from:
`https://raw.githubusercontent.com/home-assistant/developers.home-assistant/refs/heads/master/docs/core/integration-quality-scale/rules/{rule_name}.md`
where `{rule_name}` is the rule identifier (e.g. `config-flow`, `entity-unique-id`, `parallel-updates`).

## 2. Understand rule requirements
Parse the rule documentation to identify:
- Core requirements and mandatory implementations
- Specific code patterns or configurations required
- Common violations and anti-patterns
- Exemption criteria (when a rule might not apply)
- The quality tier this rule belongs to (Bronze, Silver, Gold, Platinum)

## 3. Analyze the integration code
Examine the integration's codebase at `homeassistant/components/<integration domain>`, focusing on:
- `manifest.json` for quality scale declaration and configuration
- `quality_scale.yaml` for rule status (done, todo, exempt)
- Relevant Python modules based on the rule requirements
- Configuration files and service definitions as needed

Additional sources:
- Integration docs: WebFetch `https://raw.githubusercontent.com/home-assistant/home-assistant.io/refs/heads/current/source/_integrations/<integration domain>.markdown`
- PyPI package info: `https://pypi.org/pypi/<package>/json`

## 4. Verification process
- Check if the rule is marked `done`, `todo`, or `exempt` in `quality_scale.yaml`
- If marked `exempt`, verify the exemption reason is valid
- If marked `done`, verify the actual implementation matches the requirements
- Identify specific files and code sections that demonstrate compliance or violations
- Consider the integration's declared quality tier when applying rules
- Look for the exact implementation patterns specified in the rule
- Check for common mistakes, anti-patterns, edge cases, and error handling requirements
- Validate that implementations follow Home Assistant conventions

Quality scale rules are cumulative: Bronze rules apply to all integrations with a quality scale, Silver rules apply to Silver+ integrations, and so on. Always consider the integration's target quality level when determining which rules to enforce.

## 5. Report findings
Report only the rules that have issues. Do not list rules that pass or that are validly exempt. For each rule with an issue, provide:
- **Rule**: The rule identifier and the problem (non-compliance, or an invalid/unjustified exemption)
- **Evidence**: Specific file locations and code showing the violation
- **Recommendation**: Actionable steps to achieve compliance

If no rules have issues, say so in a single line. Be thorough but focused: examine only the aspects relevant to the rules being verified. If you cannot access the rule documentation or find the integration code, clearly state what information is missing and what you would need to complete the verification.
