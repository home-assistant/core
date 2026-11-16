"""Issues for System Bridge integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN


@callback
def async_deprecated_notify_action_call(hass: HomeAssistant, service_name: str) -> None:
    """Create an issue for a call to the deprecated legacy notify action."""
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_notify_action_{service_name}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_notify_action",
        translation_placeholders={
            "action": f"notify.{service_name}",
            "new_action_1": "notify.send_message",
            "new_action_2": "system_bridge.send_message",
            "example_yaml_1": """
```yaml
action: notify.send_message
target:
  entity_id: notify.my_computer
data:
  title: Hello
  message: Hello World
```
""",
            "example_yaml_2": """
```yaml
action: system_bridge.send_message
target:
  entity_id: notify.my_computer
data:
  title: Hello
  message: Hello World
  urgency: critical
  duration:
    seconds: 10
  buttons:
    - id: open
      label: Open
```
""",
        },
    )
