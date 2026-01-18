# Diagnostics

This skill covers implementing diagnostics and repair issues for Home Assistant integrations.

## When to Use

- Adding diagnostic data collection (Gold requirement)
- Creating actionable repair issues
- Debugging integration problems

## Diagnostics Implementation

Create `diagnostics.py`:

```python
"""Diagnostics support for My Integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE

from . import MyIntegrationConfigEntry

TO_REDACT = {
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    "password",
    "token",
    "access_token",
    "refresh_token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "coordinator_data": async_redact_data(
            coordinator.data.to_dict(), TO_REDACT
        ),
    }
```

## Security Requirements

**Never expose:**
- Passwords
- API keys / tokens
- GPS coordinates (latitude/longitude)
- Personal identifiers

Always use `async_redact_data()` for sensitive fields.

## Repair Issues

### Creating Issues

```python
from homeassistant.helpers import issue_registry as ir

ir.async_create_issue(
    hass,
    DOMAIN,
    "outdated_firmware",
    is_fixable=False,
    issue_domain=DOMAIN,
    severity=ir.IssueSeverity.ERROR,
    translation_key="outdated_firmware",
    translation_placeholders={
        "current_version": device.firmware,
        "min_version": MIN_FIRMWARE_VERSION,
    },
)
```

### Actionable Issues Required

All repair issues MUST be actionable for end users. Include:
- What the problem is
- Why it matters
- Exact steps to resolve (numbered list when multiple steps)
- What to expect after following the steps

### strings.json for Issues

```json
{
  "issues": {
    "outdated_firmware": {
      "title": "Device firmware is outdated",
      "description": "Your device firmware version {current_version} is below the minimum required version {min_version}.\n\nTo fix this issue:\n1. Open the manufacturer's mobile app\n2. Navigate to device settings\n3. Select 'Update Firmware'\n4. Wait for the update to complete\n5. Restart Home Assistant"
    },
    "api_deprecated": {
      "title": "API version deprecated",
      "description": "The API version used by your device will stop working in Home Assistant {breaks_in_ha_version}.\n\nTo resolve this:\n1. Check for device firmware updates\n2. Contact the manufacturer if no update is available"
    }
  }
}
```

### Severity Levels

| Level | Use For |
|-------|---------|
| `CRITICAL` | Extreme scenarios only |
| `ERROR` | Requires immediate user attention |
| `WARNING` | Indicates future potential breakage |

### Additional Issue Attributes

```python
ir.async_create_issue(
    hass,
    DOMAIN,
    "deprecated_feature",
    breaks_in_ha_version="2024.6.0",
    is_fixable=True,
    is_persistent=True,
    severity=ir.IssueSeverity.WARNING,
    translation_key="deprecated_feature",
)
```

### Fixable Issues

For issues that can be fixed automatically:

```python
# In repairs.py
from homeassistant.components.repairs import RepairsFlow

class MyRepairFlow(RepairsFlow):
    """Handler for fixable repair issue."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of the repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the confirm step."""
        if user_input is not None:
            # Perform the fix
            await self._async_fix_issue()
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm")

    async def _async_fix_issue(self) -> None:
        """Fix the issue."""
        # Implementation here
```

### Deleting Issues

When the problem is resolved:

```python
ir.async_delete_issue(hass, DOMAIN, "outdated_firmware")
```

## Testing Diagnostics

```python
"""Test diagnostics."""

from homeassistant.components.diagnostics import async_get_config_entry_diagnostics

from tests.components.my_integration.conftest import init_integration


async def test_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics output."""
    await init_integration(hass, mock_config_entry)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["entry_data"]["host"] == "192.168.1.100"
    assert result["entry_data"]["api_key"] == "**REDACTED**"
```

## Related Skills

- `quality-scale` - Diagnostics is a Gold requirement
- `write-tests` - Testing diagnostics
