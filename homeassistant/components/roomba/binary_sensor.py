"""Roomba binary sensor entities."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import roomba_reported_state
from .entity import IRobotEntity
from .models import RoombaConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoombaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data = config_entry.runtime_data
    roomba = domain_data.roomba
    blid = domain_data.blid
    entities: list[BinarySensorEntity] = [RoombaCharging(roomba, blid)]
    reported = roomba_reported_state(roomba)
    status = reported.get("bin", {})
    if "full" in status:
        entities.append(RoombaBinStatus(roomba, blid))
    entities.extend(
        RoombaDockCapability(roomba, blid, api_key, translation_key)
        for api_key, translation_key in (
            ("evacAllowed", "bin_empty_allowed"),
            ("padWashAllowed", "pad_wash_allowed"),
            ("padDryAllowed", "pad_dry_allowed"),
        )
        if api_key in reported
    )
    async_add_entities(entities)


class RoombaDockCapability(IRobotEntity, BinarySensorEntity):
    """Reports whether the dock currently permits an action."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, roomba, blid: str, api_key: str, translation_key: str) -> None:
        """Initialize the capability binary sensor."""
        super().__init__(roomba, blid)
        self._api_key = api_key
        self._attr_translation_key = translation_key

    @property
    @override
    def unique_id(self) -> str:
        """Return the ID of this sensor.

        Keyed on the reported field rather than the translation key: the
        translation key is presentation and can be reworded, which would
        change the entity's identity.
        """
        return f"{self._api_key}_{self._blid}"

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the dock currently permits this action."""
        return roomba_reported_state(self.vacuum).get(self._api_key) in (True, 1)

    @override
    def new_state_filter(self, new_state):
        """Filter the new state."""
        return self._api_key in new_state


class RoombaBinStatus(IRobotEntity, BinarySensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_translation_key = "bin_full"

    @property
    @override
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"bin_{self._blid}"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return roomba_reported_state(self.vacuum).get("bin", {}).get("full", False)

    @override
    def new_state_filter(self, new_state):
        """Filter the new state."""
        return "bin" in new_state


class RoombaCharging(IRobotEntity, BinarySensorEntity):
    """Class to hold Roomba charging status."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    @override
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"charging_{self._blid}"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return (
            roomba_reported_state(self.vacuum)
            .get("cleanMissionStatus", {})
            .get("phase")
            == "charge"
        )

    @override
    def new_state_filter(self, new_state):
        """Filter the new state."""
        return "cleanMissionStatus" in new_state
