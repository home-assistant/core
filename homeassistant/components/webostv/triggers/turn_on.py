"""LG webOS TV device turn on trigger."""

from functools import partial
from typing import TYPE_CHECKING, Any, cast, override

import probatio

from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import move_top_level_schema_fields_to_options
from homeassistant.helpers.trigger import (
    PluggableAction,
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from ..const import DOMAIN
from ..helpers import (
    async_get_device_entry_by_device_id,
    async_get_device_id_from_entity_id,
)

# Stored in device automations as the trigger type; must stay stable
PLATFORM_TYPE = f"{DOMAIN}.turn_on"

_OPTIONS_SCHEMA_DICT: dict[probatio.Marker, Any] = {
    probatio.Optional(ATTR_DEVICE_ID): probatio.All(probatio.EnsureList(), [cv.string]),
    probatio.Optional(ATTR_ENTITY_ID): cv.entity_ids,
}

_TRIGGER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_OPTIONS): probatio.All(
            _OPTIONS_SCHEMA_DICT,
            probatio.AtLeastOne(ATTR_ENTITY_ID, ATTR_DEVICE_ID),
        )
    }
)


def async_get_turn_on_trigger(device_id: str) -> dict[str, str]:
    """Return data for a turn on trigger."""

    return {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: PLATFORM_TYPE,
    }


@callback
def async_get_turn_on_description(hass: HomeAssistant, device_id: str) -> str:
    """Return the trigger description for a device."""
    device = async_get_device_entry_by_device_id(hass, device_id)
    return f"webostv turn on trigger for {device.name_by_user or device.name}"


class TurnOnTrigger(Trigger):
    """LG webOS TV turn on trigger."""

    _options: dict[str, Any]

    @classmethod
    @override
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config, moving legacy fields to options."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)

        if TYPE_CHECKING:
            assert config.options is not None
        self._options = config.options

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""
        device_ids = set(self._options.get(ATTR_DEVICE_ID, []))
        device_ids.update(
            async_get_device_id_from_entity_id(self._hass, entity_id)
            for entity_id in self._options.get(ATTR_ENTITY_ID, [])
        )

        async def run_turn_on_action(
            description: str,
            variables: dict[str, Any],
            context: Context | None = None,
        ) -> None:
            """Run the action; a coroutine so turn_on can await it."""
            await run_action(variables, description, context)

        unsubs = [
            PluggableAction.async_attach_trigger(
                self._hass,
                async_get_turn_on_trigger(device_id),
                partial(
                    run_turn_on_action,
                    async_get_turn_on_description(self._hass, device_id),
                ),
                {ATTR_DEVICE_ID: device_id},
            )
            for device_id in device_ids
        ]

        @callback
        def async_remove() -> None:
            """Remove the attached actions."""
            for unsub in unsubs:
                unsub()
            unsubs.clear()

        return async_remove
