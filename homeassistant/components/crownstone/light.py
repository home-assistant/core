"""Support for Crownstone devices."""
from __future__ import annotations

from collections.abc import Mapping
from functools import partial
import logging
from typing import TYPE_CHECKING, Any

from crownstone_cloud.cloud_models.crownstones import Crownstone
from crownstone_cloud.const import (
    DIMMING_ABILITY,
    SWITCHCRAFT_ABILITY,
    TAP_TO_TOGGLE_ABILITY,
)
from crownstone_cloud.exceptions import CrownstoneAbilityError
from crownstone_uart import CrownstoneUart

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ABILITY_STATE,
    CROWNSTONE_INCLUDE_TYPES,
    CROWNSTONE_SUFFIX,
    DOMAIN,
    SIG_CROWNSTONE_STATE_UPDATE,
    SIG_UART_STATE_CHANGE,
)
from .devices import CrownstoneDevice
from .helpers import map_from_to

if TYPE_CHECKING:
    from .entry_manager import CrownstoneEntryManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up crownstones from a config entry."""
    manager: CrownstoneEntryManager = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[CrownstoneEntity] = []

    # Add Crownstone entities that support switching/dimming
    for sphere in manager.cloud.cloud_data:
        for crownstone in sphere.crownstones:
            if crownstone.type in CROWNSTONE_INCLUDE_TYPES:
                # Crownstone can communicate with Crownstone USB
                if manager.uart and sphere.cloud_id == manager.usb_sphere_id:
                    entities.append(CrownstoneEntity(crownstone, manager.uart))
                # Crownstone can't communicate with Crownstone USB
                else:
                    entities.append(CrownstoneEntity(crownstone))

    async_add_entities(entities)


def crownstone_state_to_hass(value: int) -> int:
    """Crownstone 0..100 to hass 0..255."""
    return map_from_to(value, 0, 100, 0, 255)


def hass_to_crownstone_state(value: int) -> int:
    """Hass 0..255 to Crownstone 0..100."""
    return map_from_to(value, 0, 255, 0, 100)


class CrownstoneEntity(CrownstoneDevice, LightEntity):
    """
    Representation of a crownstone.

    Light platform is used to support dimming.
    """

    _attr_should_poll = False
    _attr_icon = "mdi:power-socket-de"

    def __init__(self, crownstone_data: Crownstone, usb: CrownstoneUart = None) -> None:
        """Initialize the crownstone."""
        super().__init__(crownstone_data)
        self.usb = usb
        # Entity class attributes
        self._attr_name = str(self.device.name)
        self._attr_unique_id = f"{self.cloud_id}-{CROWNSTONE_SUFFIX}"

    @property
    def usb_available(self) -> bool:
        """Return if this entity can use a usb dongle."""
        return self.usb is not None and self.usb.is_ready()

    @property
    def brightness(self) -> int | None:
        """Return the brightness if dimming enabled."""
        return crownstone_state_to_hass(self.device.state)

    @property
    def is_on(self) -> bool:
        """Return if the device is on."""
        return crownstone_state_to_hass(self.device.state) > 0

    @property
    def supported_features(self) -> int:
        """Return the supported features of this Crownstone."""
        if self.device.abilities.get(DIMMING_ABILITY).is_enabled:
            return SUPPORT_BRIGHTNESS
        return 0

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """State attributes for Crownstone devices."""
        attributes: dict[str, Any] = {}
        # switch method
        if self.usb_available:
            attributes["switch_method"] = "Crownstone USB Dongle"
        else:
            attributes["switch_method"] = "Crownstone Cloud"

        # crownstone abilities
        attributes["dimming"] = ABILITY_STATE.get(
            self.device.abilities.get(DIMMING_ABILITY).is_enabled
        )
        attributes["tap_to_toggle"] = ABILITY_STATE.get(
            self.device.abilities.get(TAP_TO_TOGGLE_ABILITY).is_enabled
        )
        attributes["switchcraft"] = ABILITY_STATE.get(
            self.device.abilities.get(SWITCHCRAFT_ABILITY).is_enabled
        )

        return attributes

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        # new state received
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_CROWNSTONE_STATE_UPDATE, self.async_write_ha_state
            )
        )
        # updates state attributes when usb connects/disconnects
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIG_UART_STATE_CHANGE, self.async_write_ha_state
            )
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this light via dongle or cloud."""
        if ATTR_BRIGHTNESS in kwargs:
            if self.usb_available:
                await self.hass.async_add_executor_job(
                    partial(
                        self.usb.dim_crownstone,
                        self.device.unique_id,
                        hass_to_crownstone_state(kwargs[ATTR_BRIGHTNESS]),
                    )
                )
            else:
                try:
                    await self.device.async_set_brightness(
                        hass_to_crownstone_state(kwargs[ATTR_BRIGHTNESS])
                    )
                except CrownstoneAbilityError as ability_error:
                    _LOGGER.error(ability_error)
                    return

            # assume brightness is set on device
            self.device.state = hass_to_crownstone_state(kwargs[ATTR_BRIGHTNESS])
            self.async_write_ha_state()

        elif self.usb_available:
            await self.hass.async_add_executor_job(
                partial(self.usb.switch_crownstone, self.device.unique_id, on=True)
            )
            self.device.state = 100
            self.async_write_ha_state()

        else:
            await self.device.async_turn_on()
            self.device.state = 100
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this device via dongle or cloud."""
        if self.usb_available:
            await self.hass.async_add_executor_job(
                partial(self.usb.switch_crownstone, self.device.unique_id, on=False)
            )

        else:
            await self.device.async_turn_off()

        self.device.state = 0
        self.async_write_ha_state()
