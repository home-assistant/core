"""Issues for HTML5 integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util import slugify

from .const import DOMAIN


@callback
def deprecated_notify_action_call(
    hass: HomeAssistant, target: list[str] | None
) -> None:
    """Deprecated action call."""

    action = (
        f"notify.html5_{slugify(target[0])}"
        if target and len(target) == 1
        else "notify.html5"
    )

    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_notify_action_{action}",
        breaks_in_ha_version="2026.11.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_notify_action",
        translation_placeholders={
            "action": action,
            "new_action_1": "notify.send_message",
            "new_action_2": "html5.send_message",
        },
    )


@callback
def deprecated_dismiss_action_call(hass: HomeAssistant) -> None:
    """Deprecated action call."""

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_dismiss_action",
        breaks_in_ha_version="2026.11.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_dismiss_action",
        translation_placeholders={
            "action": "html5.dismiss",
            "new_action": "html5.dismiss_message",
        },
    )


@callback
def deprecated_event_bus(hass: HomeAssistant, event: str) -> None:
    """Raise a deprecation issue for listeners on the event bus."""

    if listeners := hass.bus.async_listeners().get(event):
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_event_bus_{event}",
            breaks_in_ha_version="2026.11.0",
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
      - event.my_device
    not_from:
      - unavailable
conditions:
  - condition: template
    value_template: |
      "{{ trigger.to_state.attributes.event_type == 'clicked' }}"
```
""",
                "example_yaml_trigger": """```yaml
triggers:
  - trigger: event.received
    target:
      entity_id: event.my_device
    options:
      event_type:
        - received
```
""",
            },
        )
