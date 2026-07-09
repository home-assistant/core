"""Provides triggers for Easywave devices."""

from abc import ABC
from typing import cast, override

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS, CONF_TARGET
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    EVENT_EASYWAVE,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
    EVENT_TYPE_GATEWAY_CONNECTED,
    EVENT_TYPE_GATEWAY_DISCONNECTED,
)

CONF_SUBTYPE = "subtype"

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
        vol.Optional(CONF_OPTIONS, default={}): dict,
    }
)


class EasywaveEventTrigger(Trigger, ABC):
    """Listen for Easywave device automation events on the event bus."""

    _event_type: str
    _subtype: str | None = None
    _schema = _TRIGGER_SCHEMA

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, cls._schema(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        assert config.target is not None
        self._target = config.target

    def _device_ids_from_target(self) -> set[str]:
        """Return device registry IDs referenced by the trigger target."""
        referenced = async_extract_referenced_entity_ids(
            self._hass, TargetSelection(self._target), expand_group=False
        )
        device_ids = set(referenced.referenced_devices)
        for entity_id in referenced.referenced:
            if device_id := async_entity_id_to_device_id(self._hass, entity_id):
                device_ids.add(device_id)
        return device_ids

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach a bus listener for matching Easywave events."""
        device_ids = self._device_ids_from_target()
        event_type = self._event_type
        subtype = self._subtype

        @callback
        def handle_event(event: Event) -> None:
            """Fire when an Easywave event matches this trigger."""
            if event.data.get("type") != event_type:
                return
            device_id = event.data.get("device_id")
            if not isinstance(device_id, str) or device_id not in device_ids:
                return
            if subtype is not None and event.data.get(CONF_SUBTYPE) != subtype:
                return
            run_action(
                {"event": event, "device_id": device_id},
                f"Easywave {event_type}",
                event.context,
            )

        return self._hass.bus.async_listen(EVENT_EASYWAVE, handle_event)


def _make_button_press_trigger(button: str) -> type[Trigger]:
    """Create a trigger class for a specific button press."""

    class _EasywaveButtonPressTrigger(EasywaveEventTrigger):
        _event_type = EVENT_TYPE_BUTTON_PRESS
        _subtype = button

    _EasywaveButtonPressTrigger.__name__ = f"EasywaveButtonPress{button.upper()}Trigger"
    _EasywaveButtonPressTrigger.__qualname__ = _EasywaveButtonPressTrigger.__name__
    return _EasywaveButtonPressTrigger


class EasywaveButtonReleaseTrigger(EasywaveEventTrigger):
    """Listen for Easywave button release events."""

    _event_type = EVENT_TYPE_BUTTON_RELEASE
    _subtype = "released"


class EasywaveGatewayConnectedTrigger(EasywaveEventTrigger):
    """Listen for RX11 gateway connected events."""

    _event_type = EVENT_TYPE_GATEWAY_CONNECTED
    _subtype = "connected"


class EasywaveGatewayDisconnectedTrigger(EasywaveEventTrigger):
    """Listen for RX11 gateway disconnected events."""

    _event_type = EVENT_TYPE_GATEWAY_DISCONNECTED
    _subtype = "disconnected"


TRIGGERS: dict[str, type[Trigger]] = {
    "button_press_a": _make_button_press_trigger("a"),
    "button_press_b": _make_button_press_trigger("b"),
    "button_press_c": _make_button_press_trigger("c"),
    "button_press_d": _make_button_press_trigger("d"),
    "button_release": EasywaveButtonReleaseTrigger,
    "gateway_connected": EasywaveGatewayConnectedTrigger,
    "gateway_disconnected": EasywaveGatewayDisconnectedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return Easywave triggers for the target-based automation UI."""
    return TRIGGERS
