"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.media_player.const import SUPPORT_VOLUME_SET
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_MAX_VOLUME,
    CONF_RECEIVER,
    DEFAULT_MAX_VOLUME,
    DOMAIN,
    MAX_VOLUME_MAX_VALUE,
    MAX_VOLUME_MIN_VALUE,
)
from .receiver import OnkyoNetworkReceiver, ReceiverZone


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up Number platform for passed config_entry."""
    receiver: OnkyoNetworkReceiver = hass.data[DOMAIN][config_entry.entry_id][
        CONF_RECEIVER
    ]

    new_devices: list[NumberBase] = []
    for zone in receiver.zones.values():
        if zone.supported_features & SUPPORT_VOLUME_SET != 0:
            new_devices.append(OnkyoMaxVolumeNumber(zone))

    # Add all new devices to HA.
    if new_devices:
        async_add_entities(new_devices)


class NumberBase(NumberEntity):
    """Base representation of any Onkyo Number Entity."""

    should_poll: bool = False

    def __init__(self, receiver_zone: ReceiverZone) -> None:
        """Initialize the base number."""
        self._receiver_zone: ReceiverZone = receiver_zone

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._receiver_zone.receiver.identifier)},
            "name": self._receiver_zone.receiver.name,
            "model": self._receiver_zone.receiver.name,
            "manufacturer": self._receiver_zone.receiver.manufacturer,
        }

    @property
    def available(self) -> bool:
        """Return True if receiver is online."""
        return self._receiver_zone.receiver.online

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._receiver_zone.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._receiver_zone.remove_callback(self.async_write_ha_state)


class OnkyoMaxVolumeNumber(NumberBase, RestoreEntity):
    """Representation of the max volume on an Onkyo network receiver zone."""

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        if state := await self.async_get_last_state():
            # Get the last value from the extra state attributes.
            self._receiver_zone.set_max_volume(
                int(state.attributes.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME))
            )

        await super().async_added_to_hass()

    @property
    def unique_id(self) -> str:
        """Return Unique ID string."""
        return f"{self._receiver_zone.zone_identifier}_max_volume"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {CONF_MAX_VOLUME: self.value}

    @property
    def name(self) -> str:
        """Return the name of the receiver zone."""
        return f"{self._receiver_zone.name} Maximum Volume"

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return MAX_VOLUME_MIN_VALUE

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return MAX_VOLUME_MAX_VALUE

    @property
    def value(self) -> float:
        """Return the current max volume."""
        return float(self._receiver_zone.max_volume)

    async def async_set_value(self, value: float) -> None:
        """Set the max volume to this value."""
        self._receiver_zone.set_max_volume(int(value))
