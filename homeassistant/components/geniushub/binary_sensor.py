"""Support for Genius Hub binary_sensor devices."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GeniusHubConfigEntry
from .entity import GeniusDevice, GeniusZone

GH_STATE_ATTR = "outputOnOff"
GH_TYPE = "Receiver"

GH_ZONES_WITH_DEMAND = [
    "radiator",
    "wet underfloor",
    "on / off",
    "hot water temperature",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeniusHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Genius Hub binary sensor entities."""

    broker = entry.runtime_data

    entities: list[GeniusBinarySensor | GeniusZoneDemand] = [
        GeniusBinarySensor(broker, d, GH_STATE_ATTR)
        for d in broker.client.device_objs
        if GH_TYPE in d.data.get("type", "")
    ]
    entities.extend(
        GeniusZoneDemand(broker, z)
        for z in broker.client.zone_objs
        if z.data.get("type") in GH_ZONES_WITH_DEMAND
    )

    async_add_entities(entities)


class GeniusBinarySensor(GeniusDevice, BinarySensorEntity):
    """Representation of a Genius Hub binary_sensor."""

    def __init__(self, broker, device, state_attr) -> None:
        """Initialize the binary sensor."""
        super().__init__(broker, device)

        self._state_attr = state_attr

        if device.type[:21] == "Dual Channel Receiver":
            self._attr_name = f"{device.type[:21]} {device.id}"
        else:
            self._attr_name = f"{device.type} {device.id}"

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._device.data["state"][self._state_attr]


class GeniusZoneDemand(GeniusZone, BinarySensorEntity):
    """Representation of a Genius Hub zone demand binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(self, broker, zone) -> None:
        """Initialize the zone demand binary sensor."""
        super().__init__(broker, zone)

        self._unique_id = f"{broker.hub_uid}_zone_{zone.id}_demand"
        self._attr_name = f"{zone.name} Demand"

    @property
    def is_on(self) -> bool:
        """Return true if the zone is calling for heat."""
        return self._zone.data.get("output") == 1
