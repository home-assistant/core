# Skill: Improve Integration

Use this skill when improving an existing Home Assistant integration toward a higher quality scale level.

## Workflow

### Step 1: Analyze current state

1. Read `manifest.json` to find current `quality_scale` target (Bronze/Silver/Gold/Platinum)
2. Read `quality_scale.yaml` to see rule statuses:
   - `done`: Already implemented
   - `todo`: Needs implementation
   - `exempt`: Doesn't apply (check comment for reason)
3. List all rules marked as `todo`

### Step 2: Understand the rules

For each `todo` rule, fetch the official documentation:
```
https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/<rule-name>/
```

The rule documentation explains:
- What the rule requires
- How to implement it
- Examples

### Step 3: Prioritize improvements

Order by impact and complexity:

**High priority (user-visible)**:
- `entity-unavailable` - Proper availability handling
- `entity-translations` - Internationalization
- `reauthentication-flow` - Credential updates
- `reconfiguration-flow` - Config updates

**Medium priority (quality)**:
- `parallel-updates` - Specify concurrent update limit
- `diagnostics` - Debug data collection
- `devices` - Device registry integration

**Lower priority (technical)**:
- `strict-typing` - Full type hints
- `async-dependency` - Async-only dependencies

### Step 4: Implement each improvement

For each rule:

1. **Read relevant documentation**:
   - Entity issues → `.claude/docs/entity-patterns.md`
   - Config flow issues → `.claude/docs/config-flow-patterns.md`
   - Testing issues → `.claude/docs/testing-patterns.md`
   - Diagnostics → `.claude/docs/diagnostics-repairs.md`
   - Translations → `.claude/docs/translations.md`

2. **Make the changes** following the patterns

3. **Update `quality_scale.yaml`**: Change `todo` to `done`

4. **Add/update tests** if needed (>95% coverage required)

### Step 5: Validate changes

```bash
# Run linters
pre-commit run --all-files

# Run integration tests
pytest ./tests/components/<domain> \
  --cov=homeassistant.components.<domain> \
  --cov-report term-missing

# Validate project structure
python -m script.hassfest

# Update translations if strings.json changed
python -m script.translations develop --all
```

### Step 6: Update manifest if needed

When all rules for a tier are `done`, consider updating the `quality_scale` in `manifest.json` to target the next tier.

## Key Reminders

- **Don't skip tests**: All changes need test coverage
- **Check exemptions**: Some rules may legitimately not apply
- **One rule at a time**: Implement and verify each rule before moving on
- **Follow patterns**: Use the docs for consistent implementation

## Common Quality Scale Rules

| Rule | What it requires |
|------|------------------|
| `config-flow` | UI-based configuration |
| `entity-unique-id` | Stable unique IDs for all entities |
| `entity-unavailable` | Mark entities unavailable when data fetch fails |
| `parallel-updates` | Set `PARALLEL_UPDATES` constant |
| `reauthentication-flow` | Allow credential updates |
| `reconfiguration-flow` | Allow config updates |
| `diagnostics` | Implement diagnostic data collection |
| `devices` | Register devices in device registry |
| `entity-translations` | Translate entity names |
| `strict-typing` | Full type hints with typed config entry |
