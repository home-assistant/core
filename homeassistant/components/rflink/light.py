"""Support for Rflink lights."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_ALIASES,
    CONF_AUTOMATIC_ADD,
    CONF_DEVICE_DEFAULTS,
    CONF_FIRE_EVENT,
    CONF_GROUP,
    CONF_GROUP_ALIASES,
    CONF_NOGROUP_ALIASES,
    CONF_SIGNAL_REPETITIONS,
    DATA_DEVICE_REGISTER,
    DEVICE_DEFAULTS_SCHEMA,
    EVENT_KEY_COMMAND,
    EVENT_KEY_ID,
    SwitchableRflinkDevice,
)
from .utils import brightness_to_rflink, rflink_to_brightness

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

TYPE_DIMMABLE = "dimmable"
TYPE_SWITCHABLE = "switchable"
TYPE_HYBRID = "hybrid"
TYPE_TOGGLE = "toggle"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})
        ): DEVICE_DEFAULTS_SCHEMA,
        vol.Optional(CONF_AUTOMATIC_ADD, default=True): cv.boolean,
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_TYPE): vol.Any(
                        TYPE_DIMMABLE, TYPE_SWITCHABLE, TYPE_HYBRID, TYPE_TOGGLE
                    ),
                    vol.Optional(CONF_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_GROUP_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_NOGROUP_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_FIRE_EVENT): cv.boolean,
                    vol.Optional(CONF_SIGNAL_REPETITIONS): vol.Coerce(int),
                    vol.Optional(CONF_GROUP, default=True): cv.boolean,
                }
            )
        },
    },
    extra=vol.ALLOW_EXTRA,
)


def entity_type_for_device_id(device_id):
    """Return entity class for protocol of a given device_id.

    Async friendly.
    """
    entity_type_mapping = {
        # KlikAanKlikUit support both dimmers and on/off switches on the same
        # protocol
        "newkaku": TYPE_HYBRID
    }
    protocol = device_id.split("_")[0]
    return entity_type_mapping.get(protocol)


def entity_class_for_type(entity_type):
    """Translate entity type to entity class.

    Async friendly.
    """
    entity_device_mapping = {
        # sends only 'dim' commands not compatible with on/off switches
        TYPE_DIMMABLE: DimmableRflinkLight,
        # sends only 'on/off' commands not advices with dimmers and signal
        # repetition
        TYPE_SWITCHABLE: RflinkLight,
        # sends 'dim' and 'on' command to support both dimmers and on/off
        # switches. Not compatible with signal repetition.
        TYPE_HYBRID: HybridRflinkLight,
        # sends only 'on' commands for switches which turn on and off
        # using the same 'on' command for both.
        TYPE_TOGGLE: ToggleRflinkLight,
    }

    return entity_device_mapping.get(entity_type, RflinkLight)


def devices_from_config(domain_config):
    """Parse configuration and add Rflink light devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        # Determine which kind of entity to create
        if CONF_TYPE in config:
            # Remove type from config to not pass it as and argument to entity
            # instantiation
            entity_type = config.pop(CONF_TYPE)
        else:
            entity_type = entity_type_for_device_id(device_id)
        entity_class = entity_class_for_type(entity_type)

        device_config = dict(domain_config[CONF_DEVICE_DEFAULTS], **config)

        is_hybrid = entity_class is HybridRflinkLight

        # Make user aware this can cause problems
        repetitions_enabled = device_config[CONF_SIGNAL_REPETITIONS] != 1
        if is_hybrid and repetitions_enabled:
            _LOGGER.warning(
                "Hybrid type for %s not compatible with signal "
                "repetitions. Please set 'dimmable' or 'switchable' "
                "type explicitly in configuration",
                device_id,
            )

        device = entity_class(device_id, **device_config)
        devices.append(device)

    return devices


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Rflink light platform."""
    async_add_entities(devices_from_config(config))

    async def add_new_device(event):
        """Check if device is known, otherwise add to list of known devices."""
        device_id = event[EVENT_KEY_ID]

        entity_type = entity_type_for_device_id(event[EVENT_KEY_ID])
        entity_class = entity_class_for_type(entity_type)

        device_config = config[CONF_DEVICE_DEFAULTS]
        device = entity_class(device_id, initial_event=event, **device_config)
        async_add_entities([device])

    if config[CONF_AUTOMATIC_ADD]:
        hass.data[DATA_DEVICE_REGISTER][EVENT_KEY_COMMAND] = add_new_device


class RflinkLight(SwitchableRflinkDevice, LightEntity):
    """Representation of a Rflink light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}


class DimmableRflinkLight(SwitchableRflinkDevice, LightEntity):
    """Rflink light device that support dimming."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _brightness = 255

    async def async_added_to_hass(self) -> None:
        """Restore RFLink light brightness attribute."""
        await super().async_added_to_hass()

        old_state = await self.async_get_last_state()
        if (
            old_state is not None
            and old_state.attributes.get(ATTR_BRIGHTNESS) is not None
        ):
            # restore also brightness in dimmables devices
            self._brightness = int(old_state.attributes[ATTR_BRIGHTNESS])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # rflink only support 16 brightness levels
            self._brightness = rflink_to_brightness(
                brightness_to_rflink(kwargs[ATTR_BRIGHTNESS])
            )

        # Turn on light at the requested dim level
        await self._async_handle_command("dim", self._brightness)

    def _handle_event(self, event):
        """Adjust state if Rflink picks up a remote command for this device."""
        self.cancel_queued_send_commands()

        command = event["command"]
        if command in ["on", "allon"]:
            self._state = True
        elif command in ["off", "alloff"]:
            self._state = False
        # dimmable device accept 'set_level=(0-15)' commands
        elif re.search("^set_level=(0?[0-9]|1[0-5])$", command, re.IGNORECASE):
            self._brightness = rflink_to_brightness(int(command.split("=")[1]))
            self._state = True

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness


class HybridRflinkLight(DimmableRflinkLight):
    """Rflink light device that sends out both dim and on/off commands.

    Used for protocols which support lights that are not exclusively on/off
    style. For example KlikAanKlikUit supports both on/off and dimmable light
    switches using the same protocol. This type allows unconfigured
    KlikAanKlikUit devices to support dimming without breaking support for
    on/off switches.

    This type is not compatible with signal repetitions as the 'dim' and 'on'
    command are send sequential and multiple 'on' commands to a dimmable
    device can cause the dimmer to switch into a pulsating brightness mode.
    Which results in a nice house disco :)
    """

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on and set dim level."""
        await super().async_turn_on(**kwargs)
        # if the receiving device does not support dimlevel this
        # will ensure it is turned on when full brightness is set
        if self.brightness == 255:
            await self._async_handle_command("turn_on")


class ToggleRflinkLight(RflinkLight):
    """Rflink light device which sends out only 'on' commands.

    Some switches like for example Livolo light switches use the
    same 'on' command to switch on and switch off the lights.
    If the light is on and 'on' gets sent, the light will turn off
    and if the light is off and 'on' gets sent, the light will turn on.
    """

    def _handle_event(self, event):
        """Adjust state if Rflink picks up a remote command for this device."""
        self.cancel_queued_send_commands()

        if event["command"] == "on":
            # if the state is unknown or false, it gets set as true
            # if the state is true, it gets set as false
            self._state = self._state in [None, False]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._async_handle_command("toggle")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._async_handle_command("toggle")
