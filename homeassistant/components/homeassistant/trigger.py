"""Home Assistant trigger dispatcher."""

from typing import cast, override

import probatio

from homeassistant.config import DATA_PREVIOUS_VERSION
from homeassistant.const import CONF_PLATFORM, EVENT_HOMEASSISTANT_STARTED, __version__
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerActionType,
    TriggerInfo,
    TriggerNotTriggeredReporter,
    TriggerProtocol,
)
from homeassistant.helpers.typing import ConfigType

_UPDATED_TRIGGER_SCHEMA = probatio.Schema({})


async def _async_get_trigger_platform(
    hass: HomeAssistant, platform_name: str
) -> TriggerProtocol:
    """Get trigger platform from cache or import it."""
    platform = await async_import_module(
        hass, f"homeassistant.components.homeassistant.triggers.{platform_name}"
    )
    return cast(TriggerProtocol, platform)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    platform = await _async_get_trigger_platform(hass, config[CONF_PLATFORM])
    if hasattr(platform, "async_validate_trigger_config"):
        return await platform.async_validate_trigger_config(hass, config)

    return platform.TRIGGER_SCHEMA(config)  # type: ignore[no-any-return]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach trigger of specified platform."""
    platform = await _async_get_trigger_platform(hass, config[CONF_PLATFORM])
    return await platform.async_attach_trigger(hass, config, action, trigger_info)


class HomeAssistantUpdatedTrigger(Trigger):
    """Trigger that fires once after Home Assistant started on a new version."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _UPDATED_TRIGGER_SCHEMA(config))

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        unsub: CALLBACK_TYPE | None = None

        @callback
        def remove() -> None:
            if unsub is not None:
                unsub()

        if (previous_version := self._hass.data.get(DATA_PREVIOUS_VERSION)) is None:
            return remove

        @callback
        def hass_started(_: Event) -> None:
            nonlocal unsub
            unsub = None
            # A downgrade, like restoring an older backup, counts as well
            run_action(
                {"from_version": previous_version, "to_version": __version__},
                "Home Assistant updated",
            )

        # Only fires if armed before Home Assistant started, like the start
        # event of the legacy trigger.
        unsub = self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, hass_started
        )
        return remove


TRIGGERS: dict[str, type[Trigger]] = {
    "updated": HomeAssistantUpdatedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the new-style triggers for Home Assistant."""
    return TRIGGERS
