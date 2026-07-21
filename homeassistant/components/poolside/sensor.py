"""Sensor platform for Poolside body-of-water telemetry."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PoolsideConfigEntry
from .client import PoolsideClient
from .const import CURRENT_TEMPERATURE_FIELD
from .entity import PoolsideGroupEntity
from .models import PoolsideGroup


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a temperature sensor for every body of water."""
    data = entry.runtime_data
    groups = {control.group.uuid: control.group for control in data.controls}
    async_add_entities(
        PoolsideWaterTemperatureSensor(data.client, group, body_of_water_uuid)
        for group in groups.values()
        if (body_of_water_uuid := group.body_of_water_uuid) is not None
    )


class PoolsideWaterTemperatureSensor(PoolsideGroupEntity, SensorEntity):
    """The last reported temperature of a body of water.

    Confirmed telemetry pushed by the controller, keyed by the group's
    BodyOfWaterUUID rather than any control's UUID.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    # All temperatures on this wire are degrees Fahrenheit.
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

    def __init__(
        self, client: PoolsideClient, group: PoolsideGroup, body_of_water_uuid: str
    ) -> None:
        """Set up the sensor for a given body of water."""
        super().__init__(client, group)
        self._body_of_water_uuid = body_of_water_uuid
        self._attr_unique_id = (
            f"{client.controller_uuid}_{body_of_water_uuid}_temperature"
        )

    @override
    def _status_keys(self) -> set[str]:
        """Return the body-of-water key its telemetry arrives under."""
        return {self._body_of_water_uuid}

    @property
    @override
    def native_value(self) -> float | None:
        """Return the body of water's last reported temperature."""
        value = self._client.get_status(
            self._body_of_water_uuid, CURRENT_TEMPERATURE_FIELD
        )
        return None if value is None else float(value)
