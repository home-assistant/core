# Home Assistant Core Development

This repository contains the core of Home Assistant, a Python 3 based home automation application.

## Python Requirements

- **Compatibility**: Python 3.13+
- **Language**: American English for all code, comments, and documentation
- **Features**: Use newest features (pattern matching, type hints, f-strings, dataclasses, walrus operator)

## File Locations

- **Integration code**: `homeassistant/components/<domain>/`
- **Integration tests**: `tests/components/<domain>/`
- **Shared constants**: `homeassistant/const.py`
- **Quality scale rules**: `homeassistant/components/<domain>/quality_scale.yaml`

## Code Quality Tools

- **Formatting**: Ruff
- **Linting**: PyLint and Ruff
- **Type checking**: MyPy
- **Testing**: pytest with >95% coverage

**Always address underlying issues** before adding `# type: ignore`, `noqa`, or suppressions.

## Quality Scale

Check `manifest.json` for `quality_scale` target (Bronze/Silver/Gold/Platinum).
Check `quality_scale.yaml` for rule status: `done`, `todo`, or `exempt`.

**Bronze rules are always mandatory.** Higher tiers apply only if targeting that level.

## Development Commands

### Testing
```bash
# Integration tests with coverage
pytest ./tests/components/<domain> \
  --cov=homeassistant.components.<domain> \
  --cov-report term-missing \
  --numprocesses=auto

# Quick test of changed files
pytest --timeout=10 --picked

# Update snapshots (then run again without flag to verify)
pytest ./tests/components/<domain> --snapshot-update
```

### Validation
```bash
# Run all linters
pre-commit run --all-files

# Validate project structure
python -m script.hassfest

# Update translations after strings.json changes
python -m script.translations develop --all

# Update requirements after dependency changes
python -m script.gen_requirements_all
```

## Key Patterns

### Runtime Data
```python
type MyIntegrationConfigEntry = ConfigEntry[MyClient]

async def async_setup_entry(hass: HomeAssistant, entry: MyIntegrationConfigEntry) -> bool:
    client = MyClient(entry.data[CONF_HOST])
    entry.runtime_data = client
```

### Coordinator
```python
class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass, logger=LOGGER, name=DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,  # Always pass this
        )
```

### Entity Base
```python
class MyEntity(CoordinatorEntity[MyCoordinator]):
    _attr_has_entity_name = True
```

### Unique IDs
- Use: serial numbers, MAC addresses, physical IDs
- Never use: IP addresses, hostnames, device names

## Critical Rules

- **Polling intervals**: NOT user-configurable (integration determines)
- **Config entry names**: NOT set in config flows (auto-generated)
- **Blocking calls**: Use `hass.async_add_executor_job()` for blocking I/O
- **Error handling**: Keep try blocks minimal, process data outside
- **Bare exceptions**: Only allowed in config flows and background tasks
- **Sensitive data**: Never expose in diagnostics (use `async_redact_data`)
- **Tests**: Never access `hass.data` directly, use fixtures

## Code Review Guidelines

**Do NOT comment on:**
- Missing imports (static analysis catches these)
- Code formatting (Ruff handles this)

**Git practices:**
- Do NOT amend/squash/rebase commits after review starts

## Available Skills

Invoke with `/skill-name`:

| Skill | Purpose |
|-------|---------|
| `/improve-integration` | Workflow for improving integration quality scale |
| `/test-integration` | Testing patterns and commands |
| `/add-entity` | Adding new entity types |
| `/add-config-flow` | Config flow implementation |

## Available Agents

| Agent | Purpose |
|-------|---------|
| `/quality-scale-rule-verifier` | Verify specific quality scale rules |

## Reference Documentation

Detailed patterns available in `.claude/docs/`:

| Document | Content |
|----------|---------|
| `async-patterns.md` | Async programming, executors, coordinators |
| `entity-patterns.md` | Entity development, availability, lifecycle |
| `advanced-entity-patterns.md` | Custom descriptions, type casting, multi-coordinator |
| `config-flow-patterns.md` | Config flow implementation |
| `discovery-patterns.md` | Zeroconf, SSDP, Bluetooth, DHCP |
| `testing-patterns.md` | Fixtures, mocks, snapshots |
| `services-patterns.md` | Service registration and actions |
| `device-management.md` | Device registry patterns |
| `diagnostics-repairs.md` | Diagnostics and repair issues |
| `translations.md` | Entity, exception, icon translations |
| `anti-patterns.md` | Common mistakes and solutions |

See `.claude/docs/README.md` for full index.
