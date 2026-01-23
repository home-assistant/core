---
title: "Automations"
---

:::warning
The features in this page are still in very active development and should not be used yet by integrations. The API may change without a deprecation notice.
:::

## Triggers

Triggers start automations based on events, state changes, or conditions. Implement them in the `trigger` platform (`trigger.py`) of your integration by creating and registering trigger classes.

### Trigger class

Each trigger must inherit from `homeassistant.helpers.trigger.Trigger` and implement `async_validate_config` and `async_attach_runner`.
`async_validate_config` validates the configuration dict for the trigger, while
`async_attach_runner` sets up the trigger to call the provided action runner `run_action` every time the trigger fires.


Integrations that need to wait for the action to complete can await the `Task` returned by `run_action`: `await run_action(...)`.

```python
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import Trigger, TriggerActionRunner, TriggerConfig
from homeassistant.helpers.typing import ConfigType

_OPTIONS_SCHEMA = vol.Schema({
    vol.Required("event_type"): cv.string,
})

_CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_OPTIONS): _OPTIONS_SCHEMA,
})

class EventTrigger(Trigger):
    """Trigger on events."""

    _options: dict[str, Any]

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate trigger-specific config."""
        return _CONFIG_SCHEMA(config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)
        assert config.options is not None
        self._options = config.options

    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger."""
        @callback
        def async_remove() -> None:
            """Remove trigger."""
            # Your code to unregister the trigger

        @callback
        def async_on_event(event_data: dict) -> None:
            """Handle event."""
            payload = {
                "event_type": event_data["type"],
                "data": event_data["data"],
            }
            description = f"Event {event_data['type']} detected"
            run_action(payload, description)

        # Dummy example method to register your event listener
        register_for_events(async_on_event)

        return async_remove
```


### Registering triggers

Implement `async_get_triggers` in the `trigger` platform to register all the integration's triggers.
Each trigger is identified by a unique string (e.g., `"event"` in the example above).

```python
async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return triggers provided by this integration."""
    return {
        "event": EventTrigger,
    }
```


