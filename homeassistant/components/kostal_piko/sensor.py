"""Platform for Kostal Piko sensors."""
from datetime import timedelta
import logging

import async_timeout
from discord import InvalidArgument
from pykostalpiko import Piko
from pykostalpiko.dxs.entry import Descriptor
from pykostalpiko.dxs.inverter import SERIAL_NUMBER

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_CATEGORY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, SENSORS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add kostal piko sensors."""
    piko: Piko = hass.data[DOMAIN][entry.entry_id]
    coordinator = PikoCoordinator(hass, piko)

    # Subscribe to all possible sensors
    for sensor in SENSORS:
        coordinator.subscribe(sensor[0])

    await coordinator.async_config_entry_first_refresh()

    entities: list[SensorEntity] = []

    for sensor in SENSORS:
        dxs_sensor = DxsSensor(coordinator, sensor)
        entities.append(dxs_sensor)

    async_add_entities(entities)


class PikoCoordinator(DataUpdateCoordinator):
    """Update Coordinator for Kostal Piko."""

    _subscribed: list[Descriptor] = [SERIAL_NUMBER]

    def __init__(self, hass: HomeAssistant, piko: Piko) -> None:
        """Initialise the Coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )
        self.piko = piko

    def subscribe(self, *descriptors: Descriptor):
        """Add a descriptor to the data fetches."""
        self._subscribed = self._subscribed + list(descriptors)

    def unsubscribe(self, *descriptors: Descriptor):
        """Remove a descriptor from the data fetches."""
        for descriptor in descriptors:
            if descriptor == SERIAL_NUMBER:
                raise InvalidArgument("Cannot unsubscribe SERIAL_NUMBER")

            self._subscribed.remove(descriptor)

    async def _async_update_data(self):
        """Fetch latest data from the inverter."""
        async with async_timeout.timeout(10):
            return await self.piko.async_fetch_multiple(self._subscribed)


class DxsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a DxsEntry as a Sensor."""

    def __init__(
        self, coordinator: PikoCoordinator, sensor: tuple[Descriptor, dict]
    ) -> None:
        """Create a new sensor entity for a DxsEntry."""
        super().__init__(coordinator)
        dxs = sensor[0]
        props = sensor[1]

        self._entry = dxs
        self._attr_name = dxs.name
        self._attr_unique_id = f"sensor.{dxs.name}"

        if ATTR_DEVICE_CLASS in props:
            self._attr_device_class = props[ATTR_DEVICE_CLASS]

        if ATTR_UNIT_OF_MEASUREMENT in props:
            self._attr_native_unit_of_measurement = props[ATTR_UNIT_OF_MEASUREMENT]

        if ATTR_STATE_CLASS in props:
            self._attr_state_class = props[ATTR_STATE_CLASS]

        if CONF_ENTITY_CATEGORY in props:
            self._attr_entity_category = props[CONF_ENTITY_CATEGORY]

    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.data[self._entry.name]
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return the identifier for the device of this entry."""
        return {"identifiers": {(DOMAIN, self.coordinator.data[SERIAL_NUMBER.name])}}
