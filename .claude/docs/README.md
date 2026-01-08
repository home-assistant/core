# Home Assistant Integration Development Documentation

This directory contains reference documentation for developing Home Assistant integrations. These docs are loaded on-demand when needed for specific tasks.

## Available Documentation

### Core Patterns
| Document | Description | When to use |
|----------|-------------|-------------|
| [async-patterns.md](async-patterns.md) | Async programming, executors, coordinators | Working with async code, data fetching |
| [entity-patterns.md](entity-patterns.md) | Entity development, unique IDs, availability | Creating or modifying entities |
| [advanced-entity-patterns.md](advanced-entity-patterns.md) | Type casting, multi-coordinator, custom descriptions | Complex integrations with typed libraries |
| [config-flow-patterns.md](config-flow-patterns.md) | Config flow implementation examples | Adding or fixing config flows |

### Discovery & Connectivity
| Document | Description | When to use |
|----------|-------------|-------------|
| [discovery-patterns.md](discovery-patterns.md) | Zeroconf, SSDP, Bluetooth, DHCP | Implementing device discovery |
| [services-patterns.md](services-patterns.md) | Service registration and actions | Adding integration services |

### Device & State Management
| Document | Description | When to use |
|----------|-------------|-------------|
| [device-management.md](device-management.md) | Device registry, DeviceInfo | Managing device entries |
| [diagnostics-repairs.md](diagnostics-repairs.md) | Diagnostics and repair issues | Adding diagnostics or repairs |
| [translations.md](translations.md) | Entity, exception, icon translations | Internationalizing integrations |

### Testing & Quality
| Document | Description | When to use |
|----------|-------------|-------------|
| [testing-patterns.md](testing-patterns.md) | Fixtures, mocks, snapshots | Writing or fixing tests |
| [anti-patterns.md](anti-patterns.md) | Common mistakes and solutions | Code review, debugging issues |

## Usage

These documents are loaded by Claude when executing skills or when specific context is needed. You can also reference them directly in conversations:

```
Read .claude/docs/entity-patterns.md for entity development guidance
```

## Related Resources

- **Skills**: See `.claude/skills/` for workflow-based guidance
- **Agents**: See `.claude/agents/` for specialized verification agents
- **CLAUDE.md**: Essential quick reference always loaded
