""" Platform for crownstone """
import logging
from typing import Any, Dict, Optional

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CROWNSTONE_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up crownstones from a config entry"""
    crownstone_hub = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for crownstone in crownstone_hub.sphere.crownstones:
        entities.append(
            Crownstone(crownstone, crownstone_hub.uart_manager.uart_instance)
        )

    async_add_entities(entities, True)


def crownstone_brightness_to_hass(value: int):
    """Crownstone 0..1 to hass 0..255"""
    return round(value * 255)


def hass_to_crownstone_brightness(value: int):
    """Hass 0..255 to Crownstone 0..1"""
    return round(value / 255)


class Crownstone(LightEntity):
    """
    Representation of a crownstone
    Light platform is used as crownstones behave like light switches (ON/OFF state)
    Crownstones also support dimming.
    Crownstones can be used for more electronic devices, it's main use case is for lights however.
    """

    def __init__(self, crownstone, uart):
        """Initialize the crownstone"""
        self.crownstone = crownstone
        self.uart = uart

    @property
    def name(self) -> str:
        """Return the name of this crownstone"""
        return self.crownstone.name

    @property
    def icon(self) -> Optional[str]:
        """Return the icon"""
        return "mdi:power-socket-de"

    @property
    def type(self) -> str:
        """Return the crownstone type"""
        return CROWNSTONE_TYPES[self.crownstone.type]

    @property
    def unique_id(self) -> str:
        """Return the unique ID"""
        return self.crownstone.unique_id

    @property
    def cloud_id(self) -> str:
        """Return the cloud id of this crownstone"""
        return self.crownstone.cloud_id

    @property
    def should_dim(self) -> bool:
        """Return if this crownstone is able to dim"""
        return self.crownstone.dimming_enabled

    @property
    def brightness(self) -> int:
        """Return the brightness if dimming enabled"""
        return crownstone_brightness_to_hass(self.crownstone.state)

    @property
    def is_on(self) -> bool:
        """Return if the device is on"""
        return self.crownstone.state > 0

    @property
    def sw_version(self) -> str:
        """Return the firmware version on this crownstone"""
        return self.crownstone.sw_version

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Return device info"""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Crownstone",
            "model": self.type,
            "sw_version": self.sw_version,
        }

    @property
    def supported_features(self) -> int:
        if self.should_dim:
            return SUPPORT_BRIGHTNESS
        else:
            return 0

    @property
    def should_poll(self) -> bool:
        """No polling required"""
        return False

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this light via dongle or cloud"""
        if ATTR_BRIGHTNESS in kwargs:
            if self.should_dim:
                if self.crownstone.dimming_synced_to_crownstone:
                    if self.uart.is_ready():
                        self.uart.dim_crownstone(
                            self.unique_id,
                            hass_to_crownstone_brightness(int(kwargs[ATTR_BRIGHTNESS])),
                        )
                    else:
                        await self.crownstone.set_brightness(
                            hass_to_crownstone_brightness(int(kwargs[ATTR_BRIGHTNESS]))
                            * 100
                        )
                else:
                    _LOGGER.warning(
                        "Dimming is enabled but not synced to crownstone yet. Make sure to be in your "
                        "sphere and have Bluetooth enabled"
                    )
            else:
                _LOGGER.warning(
                    "Dimming is not enabled for this crownstone. Go to the crownstone app to enable it"
                )
        elif self.uart.is_ready():
            self.uart.switch_crownstone(self.unique_id, on=True)
        else:
            await self.crownstone.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this device via dongle or cloud"""
        if self.uart.is_ready():
            # switch using crownstone usb dongle
            self.uart.switch_crownstone(self.unique_id, on=False)
        else:
            # switch remotely using the cloud
            await self.crownstone.turn_off()
