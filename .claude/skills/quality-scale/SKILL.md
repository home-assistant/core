# Quality Scale

This skill explains the Integration Quality Scale and requirements for each tier.

## When to Use

- Understanding what rules apply to an integration
- Planning improvements to reach a higher tier
- Checking exemption status for rules

## Quality Scale Levels

| Level | Description |
|-------|-------------|
| **Bronze** | Basic requirements (ALL Bronze rules are mandatory) |
| **Silver** | Enhanced functionality |
| **Gold** | Advanced features |
| **Platinum** | Highest quality standards |

## How Rules Apply

1. Check `manifest.json` for `"quality_scale"` key
2. Bronze rules are always required for any integration with quality scale
3. Higher tier rules only apply if targeting that tier or higher
4. Check `quality_scale.yaml` in integration folder for rule status

## quality_scale.yaml Structure

```yaml
rules:
  # Bronze (mandatory)
  config-flow: done
  entity-unique-id: done
  action-setup:
    status: exempt
    comment: Integration does not register custom actions.

  # Silver (if targeting Silver+)
  entity-unavailable: done
  parallel-updates: done

  # Gold (if targeting Gold+)
  devices: done
  diagnostics: done

  # Platinum (if targeting Platinum)
  strict-typing: done
```

## Rule Status Values

- `done`: Rule is implemented
- `exempt`: Rule doesn't apply (requires comment explaining why)
- `todo`: Rule needs implementation

## Bronze Requirements (Mandatory)

| Rule | Description |
|------|-------------|
| `config-flow` | UI configuration via config flow |
| `entity-unique-id` | Every entity has a unique ID |
| `has-entity-name` | Entities use `has_entity_name = True` |
| `config-entry-unloading` | Implement `async_unload_entry` |
| `test-before-setup` | Verify connection in `async_setup_entry` |
| `unique-config-entry` | Prevent duplicate config entries |
| `action-setup` | Register actions in `async_setup` (not `async_setup_entry`) |

## Silver Requirements

| Rule | Description |
|------|-------------|
| `entity-unavailable` | Mark entities unavailable when data can't be fetched |
| `parallel-updates` | Set `PARALLEL_UPDATES` appropriately |
| `reauthentication-flow` | Implement `async_step_reauth` |
| `log-when-unavailable` | Log once when unavailable, once when recovered |

## Gold Requirements

| Rule | Description |
|------|-------------|
| `devices` | Group entities under devices in registry |
| `diagnostics` | Implement diagnostic data collection |
| `entity-category` | Assign appropriate categories to entities |
| `entity-device-class` | Use device classes when available |
| `entity-disabled-by-default` | Disable noisy/less popular entities |
| `entity-translations` | Support entity name translations |
| `exception-translations` | Use translation keys for exceptions |
| `icon-translations` | Support dynamic icons via translations |
| `reconfiguration-flow` | Implement `async_step_reconfigure` |
| `dynamic-devices` | Auto-detect new devices after setup |
| `stale-devices` | Auto-remove devices that disappear |
| `discovery` | Support device discovery methods |
| `repair-issues` | Create actionable repair issues |

## Platinum Requirements

| Rule | Description |
|------|-------------|
| `strict-typing` | Comprehensive type hints on all code |
| `async-dependency` | All dependencies use asyncio |
| `inject-websession` | Pass web sessions to dependencies |

## Common Exemptions

```yaml
rules:
  action-setup:
    status: exempt
    comment: Integration does not register custom actions.

  discovery:
    status: exempt
    comment: Device does not support any discovery method.

  dynamic-devices:
    status: exempt
    comment: Integration connects to a single device.

  stale-devices:
    status: exempt
    comment: Integration connects to a single device.
```

## Quality Scale Progression

1. **Bronze → Silver**: Add entity unavailability, parallel updates, reauth flows
2. **Silver → Gold**: Add device management, diagnostics, translations
3. **Gold → Platinum**: Add strict typing, async dependencies, websession injection

## Checking an Integration

```bash
# Check manifest for quality scale
cat homeassistant/components/my_integration/manifest.json | grep quality_scale

# Check quality_scale.yaml
cat homeassistant/components/my_integration/quality_scale.yaml
```

## Related Skills

- `config-flow` - Config flow (Bronze requirement)
- `entity` - Unique IDs and naming (Bronze requirements)
- `coordinator` - Parallel updates (Silver)
- `diagnostics` - Diagnostics implementation (Gold)
- `device-discovery` - Discovery methods (Gold)
