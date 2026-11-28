"""Provides triggers for Easywave devices."""

from abc import ABC
from typing import ClassVar, cast, override

import probatio

from homeassistant.const import CONF_OPTIONS, CONF_TARGET
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
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
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_BATTERY_NORMAL,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
    EVENT_TYPE_GATEWAY_CONNECTED,
    EVENT_TYPE_GATEWAY_DISCONNECTED,
    EasywaveGatewayFeature,
    EasywaveTransmitterFeature,
)

CONF_SUBTYPE = "subtype"

_TRIGGER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_TARGET): cv.TARGET_FIELDS,
        # Empty mapping: these triggers expose no options.
        probatio.Required(CONF_OPTIONS, default={}): {},
    }
)


class EasywaveEventTrigger(Trigger, ABC):
    """Listen for Easywave device automation events on the event bus."""

    _event_type: str
    _subtype: str | None = None
    _schema = _TRIGGER_SCHEMA
    # Match triggers.yaml: gateway and battery triggers include diagnostic entities.
    _primary_entities_only: ClassVar[bool] = True
    _required_feature: ClassVar[int]

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        config = cast(ConfigType, cls._schema(config))
        if not TargetSelection(config[CONF_TARGET]).has_any_target:
            raise HomeAssistantError(f"No target defined in {config[CONF_TARGET]}")
        return config

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        assert config.target is not None
        self._target = config.target

    def _device_ids_from_target(self) -> set[str]:
        """Return device registry IDs referenced by the trigger target."""
        referenced = async_extract_referenced_entity_ids(
            self._hass,
            TargetSelection(self._target),
            primary_entities_only=self._primary_entities_only,
        )
        # Only entities that carry this trigger's feature may contribute a device.
        # Otherwise a button sensor left in the area fires a battery trigger.
        registry = er.async_get(self._hass)
        device_ids: set[str] = set()
        for entity_id in referenced.referenced | referenced.indirectly_referenced:
            if (entry := registry.async_get(entity_id)) is None:
                continue
            if entry.device_id is None:
                continue
            if not entry.supported_features & self._required_feature:
                continue
            device_ids.add(entry.device_id)
        return device_ids

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach a bus listener for matching Easywave events."""
        event_type = self._event_type
        subtype = self._subtype

        @callback
        def handle_event(event: Event) -> None:
            """Fire when an Easywave event matches this trigger."""
            if event.data.get("type") != event_type:
                return
            device_id = event.data.get("device_id")
            if not isinstance(device_id, str):
                return
            if device_id not in self._device_ids_from_target():
                return
            if subtype is not None and event.data.get(CONF_SUBTYPE) != subtype:
                return
            run_action(
                {"event": event, "device_id": device_id},
                f"Easywave {event_type}",
                event.context,
            )

        return self._hass.bus.async_listen(EVENT_EASYWAVE, handle_event)


def _make_button_press_trigger(
    button: str, feature: EasywaveTransmitterFeature
) -> type[Trigger]:
    """Create a trigger class for a specific button press."""

    class _EasywaveButtonPressTrigger(EasywaveEventTrigger):
        _event_type = EVENT_TYPE_BUTTON_PRESS
        _subtype = button
        _required_feature = feature

    _EasywaveButtonPressTrigger.__name__ = f"EasywaveButtonPress{button.upper()}Trigger"
    _EasywaveButtonPressTrigger.__qualname__ = _EasywaveButtonPressTrigger.__name__
    return _EasywaveButtonPressTrigger


class EasywaveButtonReleaseTrigger(EasywaveEventTrigger):
    """Listen for Easywave button release events."""

    _event_type = EVENT_TYPE_BUTTON_RELEASE
    _subtype = "released"
    _required_feature = EasywaveTransmitterFeature.BUTTON_RELEASE


class EasywaveGatewayConnectedTrigger(EasywaveEventTrigger):
    """Listen for RX11 gateway connected events."""

    _event_type = EVENT_TYPE_GATEWAY_CONNECTED
    _subtype = "connected"
    _primary_entities_only = False
    _required_feature = EasywaveGatewayFeature.GATEWAY_STATUS


class EasywaveGatewayDisconnectedTrigger(EasywaveEventTrigger):
    """Listen for RX11 gateway disconnected events."""

    _event_type = EVENT_TYPE_GATEWAY_DISCONNECTED
    _subtype = "disconnected"
    _primary_entities_only = False
    _required_feature = EasywaveGatewayFeature.GATEWAY_STATUS


class EasywaveBatteryLowTrigger(EasywaveEventTrigger):
    """Listen for transmitter battery-low events."""

    _event_type = EVENT_TYPE_BATTERY_LOW
    _subtype = "low"
    # The battery sensor is diagnostic, so area targets must include it.
    _primary_entities_only = False
    _required_feature = EasywaveTransmitterFeature.BATTERY


class EasywaveBatteryNormalTrigger(EasywaveEventTrigger):
    """Listen for transmitter battery-ok events."""

    _event_type = EVENT_TYPE_BATTERY_NORMAL
    _subtype = "ok"
    _primary_entities_only = False
    _required_feature = EasywaveTransmitterFeature.BATTERY


TRIGGERS: dict[str, type[Trigger]] = {
    "button_press_a": _make_button_press_trigger(
        "a", EasywaveTransmitterFeature.BUTTON_A
    ),
    "button_press_b": _make_button_press_trigger(
        "b", EasywaveTransmitterFeature.BUTTON_B
    ),
    "button_press_c": _make_button_press_trigger(
        "c", EasywaveTransmitterFeature.BUTTON_C
    ),
    "button_press_d": _make_button_press_trigger(
        "d", EasywaveTransmitterFeature.BUTTON_D
    ),
    "button_release": EasywaveButtonReleaseTrigger,
    "gateway_connected": EasywaveGatewayConnectedTrigger,
    "gateway_disconnected": EasywaveGatewayDisconnectedTrigger,
    "battery_low": EasywaveBatteryLowTrigger,
    "battery_normal": EasywaveBatteryNormalTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return Easywave triggers for the target-based automation UI."""
    return TRIGGERS
