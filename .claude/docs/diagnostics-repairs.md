# Diagnostics and Repairs

## Integration Diagnostics

Implement diagnostic data collection for debugging:

```python
from homeassistant.components.diagnostics import async_redact_data

TO_REDACT = [CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_PASSWORD]

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": async_redact_data(entry.options, TO_REDACT),
        "data": entry.runtime_data.data,
    }
```

**Security**: Never expose passwords, tokens, API keys, or sensitive coordinates.

## Device Diagnostics

For per-device diagnostics:

```python
async def async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    device_id = next(
        identifier[1]
        for identifier in device.identifiers
        if identifier[0] == DOMAIN
    )
    return {
        "device_info": async_redact_data(device_data, TO_REDACT),
    }
```

## Repair Issues

All repair issues must be actionable for end users.

**Implementation**:
```python
from homeassistant.helpers import issue_registry as ir

ir.async_create_issue(
    hass,
    DOMAIN,
    "outdated_version",
    is_fixable=False,
    issue_domain=DOMAIN,
    severity=ir.IssueSeverity.ERROR,
    translation_key="outdated_version",
    translation_placeholders={
        "current_version": current_version,
        "min_version": MIN_VERSION,
    },
)
```

## Issue Content Requirements

**strings.json must include**:
- What the problem is
- Why it matters
- Exact steps to resolve (numbered list when multiple steps)
- What to expect after following the steps

```json
{
  "issues": {
    "outdated_version": {
      "title": "Device firmware is outdated",
      "description": "Your device firmware version {current_version} is below the minimum required version {min_version}. To fix this issue: 1) Open the manufacturer's mobile app, 2) Navigate to device settings, 3) Select 'Update Firmware', 4) Wait for the update to complete, then 5) Restart Home Assistant."
    }
  }
}
```

**Avoid vague instructions**: Don't just say "update firmware" - provide specific steps.

## Severity Guidelines

| Severity | Use case |
|----------|----------|
| `CRITICAL` | Reserved for extreme scenarios only |
| `ERROR` | Requires immediate user attention |
| `WARNING` | Indicates future potential breakage |

## Additional Attributes

```python
ir.async_create_issue(
    hass, DOMAIN, "issue_id",
    breaks_in_ha_version="2024.1.0",  # When it will break
    is_fixable=True,                   # Can be fixed via repair flow
    is_persistent=True,                # Survives restart
    severity=ir.IssueSeverity.ERROR,
    translation_key="issue_description",
)
```

## Fixable Issues

For issues that can be resolved through a repair flow:

```python
ir.async_create_issue(
    hass, DOMAIN, "auth_expired",
    is_fixable=True,
    severity=ir.IssueSeverity.ERROR,
    translation_key="auth_expired",
)
```

Then implement the repair flow:
```python
class MyRepairFlow(RepairsFlow):
    """Handle repair flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the repair step."""
        if user_input is not None:
            # Handle the fix
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="init")
```

## Deleting Issues

When the issue is resolved:
```python
ir.async_delete_issue(hass, DOMAIN, "issue_id")
```

## Best Practices

- Only create issues for problems users can potentially resolve
- Use friendly, helpful language
- Include relevant context (device names, error details)
- Test that the resolution steps actually work
