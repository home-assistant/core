# Claude Code Skills and Reference Files

This directory contains Claude Skills and reference documentation for working with Home Assistant integrations.

## Directory Structure

```
.claude/
├── skills/                          # Claude Skills (auto-loaded)
│   ├── testing/
│   │   └── SKILL.md                 # Testing specialist skill
│   ├── code-review/
│   │   └── SKILL.md                 # Code review specialist skill
│   └── quality-scale-architect/
│       └── SKILL.md                 # Architecture guidance skill
├── agents/                          # Legacy agent definitions
│   └── quality-scale-rule-verifier.md
└── references/                      # Deep-dive reference docs
    ├── diagnostics.md               # Diagnostics implementation
    ├── sensor.md                    # Sensor platform
    ├── binary_sensor.md             # Binary sensor platform
    ├── switch.md                    # Switch platform
    ├── button.md                    # Button platform
    ├── number.md                    # Number platform
    └── select.md                    # Select platform
```

## Claude Skills

Claude Skills are modular capabilities that extend Claude's functionality. Each Skill packages instructions and metadata that Claude uses automatically when relevant.

### How Skills Work

Skills use **progressive disclosure** - they load content in stages:

1. **Level 1 - Metadata (always loaded)**: Skill name and description
2. **Level 2 - Instructions (loaded when triggered)**: Main SKILL.md content
3. **Level 3+ - Resources (loaded as needed)**: Reference files and additional docs

This means you can have many Skills installed with minimal context penalty. Claude only knows each Skill exists and when to use it until triggered.

### Available Skills

#### Testing (`testing`)
**Use when**: Writing, running, or fixing tests for Home Assistant integrations

Specializes in:
- Writing comprehensive test coverage (>95%)
- Running pytest with appropriate flags
- Fixing failing tests and updating snapshots
- Following Home Assistant testing patterns
- Modern fixture patterns and snapshot testing

**Triggers on**: Requests about writing tests, running tests, fixing test failures, test coverage, pytest, snapshots

#### Code Review (`code-review`)
**Use when**: Reviewing code for quality, best practices, and standards compliance

Specializes in:
- Reviewing pull requests and code changes
- Identifying anti-patterns and security vulnerabilities
- Verifying async patterns and error handling
- Ensuring quality scale compliance
- Performance optimization

**Triggers on**: Requests to review code, check for issues, analyze code quality, security review

#### Quality Scale Architect (`quality-scale-architect`)
**Use when**: Needing architectural guidance and quality scale planning

Specializes in:
- High-level architecture guidance
- Quality scale tier selection (Bronze/Silver/Gold/Platinum)
- Integration structure planning
- Pattern recommendations (coordinator, push, hub)
- Progression strategies between quality tiers

**Triggers on**: Requests about architecture, integration design, quality tiers, structural planning, choosing patterns

## Reference Files

Reference files provide deep-dive documentation for specific implementation areas. Skills can reference these for detailed guidance, and they're loaded on-demand to avoid consuming context.

### Available References

- **diagnostics.md**: Complete guide to implementing integration and device diagnostics, data redaction, testing
- **sensor.md**: Sensor platform implementation, device classes, state classes, entity descriptions
- **binary_sensor.md**: Binary sensor implementation, device classes, push-updated patterns
- **switch.md**: Switch control implementation, state updates, configuration switches
- **button.md**: Button action implementation, device classes, one-time actions
- **number.md**: Numeric value control, ranges, display modes, units
- **select.md**: Option selection implementation, enums, translations, dynamic options

## How to Use

### As a Developer

Skills work automatically - just ask Claude to help with tasks:

- **Testing**: "Write tests for my sensor platform" or "Fix the failing config flow tests"
- **Review**: "Review this integration for security issues" or "Check my async patterns"
- **Architecture**: "Help me design a hub integration" or "What quality tier should I target?"

### As Claude

Skills are triggered automatically when requests match the skill descriptions. Skills can reference the documentation files in `.claude/references/` for detailed implementation guidance.

Example:
```python
# When a testing request comes in, Claude triggers the testing skill
# The skill can then reference .claude/references/sensor.md for sensor-specific patterns
```

## Quality Scale Overview

Home Assistant uses a Quality Scale system:

- **Bronze**: Basic requirements (mandatory baseline) - Config flow, unique IDs, auth flows
- **Silver**: Enhanced functionality - Unavailability tracking, runtime data, parallel updates
- **Gold**: Advanced features - Diagnostics, translations, device registry
- **Platinum**: Highest quality - Strict typing, async-only dependencies, WebSession injection

All Bronze rules are mandatory. Higher tiers are additive.

## Skill Structure

Each Skill is a directory containing a `SKILL.md` file with YAML frontmatter:

```yaml
---
name: skill-name
description: Brief description of what this Skill does and when to use it (max 1024 chars)
---

# Skill Content in Markdown

Instructions, examples, and guidance...
```

**Progressive Loading**: Only the name/description are loaded initially. The full content loads when the Skill is triggered.

## Creating Custom Skills

To add a new Skill:

1. Create a directory: `.claude/skills/my-skill/`
2. Add a `SKILL.md` file with proper frontmatter
3. Include clear instructions and examples
4. Reference existing documentation when appropriate

See [Claude Skills Documentation](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) for complete guidance.

## Additional Resources

- Main instructions: `/home/user/core/CLAUDE.md`
- Home Assistant Docs: https://developers.home-assistant.io
- Integration Quality Scale: https://developers.home-assistant.io/docs/core/integration-quality-scale/
- Claude Skills Cookbook: https://platform.claude.com/cookbook/skills-notebooks-01-skills-introduction

## Contributing

When adding new Skills or references:
1. Follow the proper Skill structure (SKILL.md with frontmatter)
2. Keep descriptions concise and trigger-focused (max 1024 chars)
3. Include practical examples in Skill content
4. Link to reference documentation for deep dives
5. Consider quality scale implications
6. Test that Skills trigger appropriately
