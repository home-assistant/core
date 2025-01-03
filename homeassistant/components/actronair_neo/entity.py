"""Sensor platform for Actron Neo integration."""

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

DIAGNOSTIC_CATEGORY = EntityCategory.DIAGNOSTIC


class EntitySensor(CoordinatorEntity, Entity):
    """Representation of a diagnostic sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        ac_unit,
        translation_key,
        path,
        key,
        device_info,
        device_class=None,
        is_diagnostic=False,
    ) -> None:
        """Initialise diagnostic sensor."""
        super().__init__(coordinator)
        self._ac_unit = ac_unit
        self._path = path if isinstance(path, list) else [path]  # Ensure path is a list
        self._key = key
        self._device_info = device_info
        self._is_diagnostic = is_diagnostic
        self._attr_device_class = device_class
        self._attr_translation_key = translation_key
        self._attr_unique_id = (
            f"{DOMAIN}_{self._ac_unit.unique_id}_sensor_{translation_key}"
        )
        self._attr_device_info = self._ac_unit.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        if data:
            # Traverse the path dynamically
            for key in self._path:
                data = data.get(key, {})
            return data.get(self._key, None)
        return None

    @property
    def device_info(self):
        """Return device information."""
        return self._device_info

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the entity category if the sensor is diagnostic."""
        return DIAGNOSTIC_CATEGORY if self._is_diagnostic else None


class BaseZoneSensor(CoordinatorEntity, Entity):
    """Base class for Actron Air Neo sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator, ac_zone, translation_key, state_key, unit_of_measurement=None
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._ac_zone = ac_zone
        self._attr_translation_key = translation_key
        self._zone_number = ac_zone.zone_number
        self._state_key = state_key
        self._unit_of_measurement = unit_of_measurement
        self._attr_unique_id = (
            f"{self._ac_zone.unique_id}_sensor_{translation_key}_{self._zone_number}"
        )
        self._attr_device_info = self._ac_zone.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        zones = self.coordinator.data.get("RemoteZoneInfo", [])
        for zone_number, zone in enumerate(zones, start=1):
            if zone_number == self._zone_number:
                return zone.get(self._state_key, None)
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement


class ZonePostionSensor(BaseZoneSensor):
    """Position sensor for Actron Air Neo zone."""

    def __init__(self, coordinator, ac_zone) -> None:
        """Initialize the position sensor."""
        super().__init__(coordinator, ac_zone, "damper_position", "ZonePosition", "%")


class ZoneTemperatureSensor(BaseZoneSensor):
    """Temperature sensor for Actron Air Neo zone."""

    def __init__(self, coordinator, ac_zone) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, ac_zone, "temperature", "LiveTemp_oC", "°C")


class ZoneHumiditySensor(BaseZoneSensor):
    """Humidity sensor for Actron Air Neo zone."""

    def __init__(self, coordinator, ac_zone) -> None:
        """Initialize the humidity sensor."""
        super().__init__(coordinator, ac_zone, "humidity", "LiveHumidity_pc", "%")


class BasePeripheralSensor(CoordinatorEntity, Entity):
    """Base class for Actron Air Neo sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        zone_peripheral,
        translation_key,
        path,
        key,
        unit_of_measurement=None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._zone_peripheral = zone_peripheral
        self._attr_translation_key = translation_key
        self._path = path if isinstance(path, list) else [path]
        self._key = key
        self._unit_of_measurement = unit_of_measurement
        self._attr_unique_id = f"{zone_peripheral.unique_id}_sensor_{translation_key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._zone_peripheral.device_info

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        # Look up the state using the state key in the data.
        data_source = self.coordinator.data.get("AirconSystem", {}).get(
            "Peripherals", []
        )
        for peripheral in data_source:
            if peripheral["LogicalAddress"] == self._zone_peripheral.logical_address():
                for key in self._path:
                    peripheral = peripheral.get(key, {})
                return peripheral.get(self._key, None)
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement


class PeripheralBatterySensor(BasePeripheralSensor):
    """Battery sensor for Actron Air Neo zone."""

    def __init__(self, coordinator, zone_peripheral) -> None:
        """Initialize the battery sensor."""
        super().__init__(
            coordinator,
            zone_peripheral,
            "battery",
            [],
            "RemainingBatteryCapacity_pc",
            "%",
        )


class PeripheralTemperatureSensor(BasePeripheralSensor):
    """Temperature sensor for Actron Air Neo zone."""

    def __init__(self, coordinator, zone_peripheral) -> None:
        """Initialize the temperature sensor."""
        super().__init__(
            coordinator,
            zone_peripheral,
            "temperature",
            ["SensorInputs", "SHTC1"],
            "Temperature_oC",
            "°C",
        )


class PeripheralHumiditySensor(BasePeripheralSensor):
    """Humidity sensor for Actron Air Neo zone."""

    def __init__(self, coordinator, zone_peripheral) -> None:
        """Initialize the humidity sensor."""
        super().__init__(
            coordinator,
            zone_peripheral,
            "humidity",
            ["SensorInputs", "SHTC1"],
            "RelativeHumidity_pc",
            "%",
        )
