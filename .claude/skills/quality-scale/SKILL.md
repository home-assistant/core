# Quality Scale

This skill explains the Integration Quality Scale and requirements for each tier.

## When to Use

- Understanding what rules apply to an integration
- Planning improvements to reach a higher tier
- Checking exemption status for rules

## Quality Scale Levels

- **Bronze**: Basic requirements (ALL Bronze rules are mandatory)
- **Silver**: Enhanced functionality 
- **Gold**: Advanced features
- **Platinum**: Highest quality standards

## How Rules Apply

1. **Check `manifest.json`**: Look for `"quality_scale"` key to determine integration level
2. **Bronze Rules**: Always required for any integration with quality scale
3. **Higher Tier Rules**: Only apply if integration targets that tier or higher
4. **Rule Status**: Check `quality_scale.yaml` in integration folder for:
   - `done`: Rule implemented
   - `exempt`: Rule doesn't apply (with reason in comment)
   - `todo`: Rule needs implementation

## Example `quality_scale.yaml` Structure

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

**When Reviewing/Creating Code**: Always check the integration's quality scale level and exemption status before applying rules.

## Quality Scale Progression

- **Bronze → Silver**: Add entity unavailability, parallel updates, auth flows
- **Silver → Gold**: Add device management, diagnostics, translations  
- **Gold → Platinum**: Add strict typing, async dependencies, websession injection

## Related Skills

- `config-flow` - Config flow (Bronze requirement)
- `entity` - Unique IDs and naming (Bronze requirements)
- `coordinator` - Parallel updates (Silver)
- `diagnostics` - Diagnostics implementation (Gold)
- `device-discovery` - Discovery methods (Gold)
