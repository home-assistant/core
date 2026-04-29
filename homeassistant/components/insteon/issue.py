"""Issues for Insteon integration."""

from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.issue_registry as ir
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN


@callback
def deprecated_event_bus(hass: HomeAssistant, event: str) -> None:
    """Raise a deprecation issue for listeners on the event bus."""

    issue_id = f"deprecated_event_bus_{event}"

    if ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None:
      if listeners := hass.bus.async_listeners().get(event):
          async_create_issue(
              hass,
              DOMAIN,
              issue_id,
              breaks_in_ha_version="2026.12.0",
              is_fixable=False,
              severity=IssueSeverity.WARNING,
              translation_key="deprecated_event_bus",
              translation_placeholders={
                  "event": event,
                  "listeners": str(listeners),
                  "example_yaml": """
```yaml
triggers:
  - trigger: state
    entity_id:
      - event.my_insteon_device_button
    attribute: event_type
    to:
      - on_fast
```
""",
                  "example_yaml_trigger": """
```yaml
triggers:
  - trigger: event.received
    target:
      entity_id: event.my_insteon_device_button
    options:
      event_type:
        - on_fast
```
""",
            },
        )
