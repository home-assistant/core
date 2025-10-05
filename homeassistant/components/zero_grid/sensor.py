"""Entities for ZeroGrid."""

from homeassistant.components.sensor import SensorEntity


class AvailableAmpsSensor(SensorEntity):
    """Current available for load control."""

    def __init__(self) -> None:
        """Initialise the sensor."""
        self._attr_name = "Available Load"
        self._attr_unique_id = "available_load"
        self._attr_native_unit_of_measurement = "A"
        self._attr_native_value = 0.0

    @property
    def native_value(self) -> float:
        """Returns the native value."""
        return self._attr_native_value

    async def update_value(self, amps: float):
        """Update the sensor value and notify HA."""
        self._attr_native_value = amps
        self.async_write_ha_state()


class LoadControlAmpsSensor(SensorEntity):
    """Total current controlled by load control."""

    def __init__(self) -> None:
        """Initialise the sensor."""
        self._attr_name = "Controlled Load"
        self._attr_unique_id = "controlled_load"
        self._attr_native_unit_of_measurement = "A"
        self._attr_native_value = 0.0

    @property
    def native_value(self) -> float:
        """Returns the native value."""
        return self._attr_native_value

    async def update_value(self, amps: float):
        """Update the sensor value and notify HA."""
        self._attr_native_value = amps
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    async_add_entities([AvailableAmpsSensor, LoadControlAmpsSensor()])
