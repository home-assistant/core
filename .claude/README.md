# Claude Code Skills and Reference Files

This directory contains specialized agents (skills) and reference documentation for working with Home Assistant integrations.

## Directory Structure

```
.claude/
├── agents/                          # Specialized AI agents
│   ├── testing.md                   # Testing specialist
│   ├── code-review.md               # Code review specialist
│   ├── quality-scale-architect.md   # Architecture guidance
│   └── quality-scale-rule-verifier.md # Rule verification
└── references/                      # Deep-dive reference docs
    ├── diagnostics.md               # Diagnostics implementation
    ├── sensor.md                    # Sensor platform
    ├── binary_sensor.md             # Binary sensor platform
    ├── switch.md                    # Switch platform
    ├── button.md                    # Button platform
    ├── number.md                    # Number platform
    └── select.md                    # Select platform
```

## Agents (Skills)

### Testing Agent (`testing.md`)
**Use when**: Writing, running, or fixing tests for Home Assistant integrations

Specializes in:
- Writing comprehensive test coverage (>95%)
- Running pytest with appropriate flags
- Fixing failing tests
- Updating test snapshots
- Following Home Assistant testing patterns

**Example usage**: "Write tests for the new sensor platform" or "Fix the failing config flow tests"

### Code Review Agent (`code-review.md`)
**Use when**: Reviewing code for quality, best practices, and standards compliance

Specializes in:
- Reviewing pull requests
- Identifying anti-patterns
- Checking for security vulnerabilities
- Verifying async patterns
- Ensuring quality scale compliance

**Example usage**: "Review my config flow implementation" or "Check this integration for security issues"

### Quality Scale Architect (`quality-scale-architect.md`)
**Use when**: Needing architectural guidance and quality scale planning

Specializes in:
- High-level architecture guidance
- Quality scale tier selection
- Integration structure planning
- Pattern recommendations
- Progression strategies (Bronze → Silver → Gold → Platinum)

**Example usage**: "What architecture should I use for my smart thermostat?" or "Help me plan progression to Gold tier"

### Quality Scale Rule Verifier (`quality-scale-rule-verifier.md`)
**Use when**: Verifying compliance with specific quality scale rules

Specializes in:
- Checking individual rule compliance
- Fetching and parsing rule documentation
- Analyzing integration code
- Providing detailed verification reports

**Example usage**: "Check if the peblar integration follows the config-flow rule" or "Verify bronze quality scale compliance"

## Reference Files

Reference files provide deep-dive documentation for specific implementation areas. Agents can reference these for detailed guidance.

### Diagnostics (`diagnostics.md`)
Complete guide to implementing integration and device diagnostics:
- Config entry diagnostics
- Device diagnostics
- Data redaction patterns
- Testing diagnostics

### Entity Platform References

#### Sensor (`sensor.md`)
- Basic sensor implementation
- Device classes and state classes
- Entity descriptions pattern
- Timestamp and enum sensors
- Long-term statistics support

#### Binary Sensor (`binary_sensor.md`)
- Binary sensor implementation
- Device classes
- Push-updated sensors
- Event-driven patterns

#### Switch (`switch.md`)
- Switch control implementation
- State update patterns
- Configuration switches
- Optimistic vs. coordinator refresh

#### Button (`button.md`)
- Button action implementation
- Device classes (restart, update, identify)
- One-time actions
- Error handling

#### Number (`number.md`)
- Numeric value control
- Range and step configuration
- Display modes (slider, box)
- Units and device classes

#### Select (`select.md`)
- Option selection implementation
- Using enums for type safety
- Option translation
- Dynamic options

## How to Use

### For Developers

When working on an integration, refer to:
1. **Agents** for task-specific help (testing, review, architecture)
2. **References** for detailed implementation guidance

### For AI Assistants

When helping with Home Assistant development:
1. Use agents via the Task tool for specialized assistance
2. Reference documentation files for implementation details
3. Agents can autonomously read reference files for deeper context

## Adding New Content

### Adding a New Agent

Create a markdown file in `agents/` with frontmatter:

```markdown
---
name: agent-name
description: |
  Description of when to use this agent...
model: inherit
color: blue
tools: Read, Write, Bash, Grep
---

Agent instructions here...
```

### Adding a New Reference

Create a markdown file in `references/` with:
- Overview section
- Implementation examples
- Common patterns
- Best practices
- Troubleshooting
- Quality scale considerations

## Quality Scale Overview

Home Assistant uses a Quality Scale system:

- **Bronze**: Basic requirements (mandatory baseline)
- **Silver**: Enhanced functionality
- **Gold**: Advanced features (diagnostics, translations)
- **Platinum**: Highest quality (strict typing, async-only)

All Bronze rules are mandatory. Higher tiers are additive.

## Additional Resources

- Main instructions: `/home/user/core/CLAUDE.md`
- Home Assistant Docs: https://developers.home-assistant.io
- Integration Quality Scale: https://developers.home-assistant.io/docs/core/integration-quality-scale/

## Contributing

When adding new agents or references:
1. Follow the existing structure and format
2. Include practical examples
3. Provide clear guidance
4. Link to official documentation
5. Consider quality scale implications
