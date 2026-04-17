"""Aquarite Sensor entities."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AquariteConfigEntry
from .const import (
    PATH_HASCD,
    PATH_HASCL,
    PATH_HASHIDRO,
    PATH_HASPH,
    PATH_HASRX,
    PATH_HASUV,
)
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aquarite sensors for every pool on the account."""
    entities: list[AquariteEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        entities.extend(_build_entities_for_coordinator(coordinator))
    async_add_entities(entities)


def _build_entities_for_coordinator(
    coordinator: AquariteDataUpdateCoordinator,
) -> list[AquariteEntity]:
    """Create all sensor entities for a single pool."""
    entities: list[AquariteEntity] = [
        AquariteTemperatureSensorEntity(coordinator, "temperature", "main.temperature"),
    ]

    if coordinator.get_value(PATH_HASCD):
        entities.append(
            AquariteValueSensorEntity(coordinator, "cd", "modules.cd.current")
        )
    if coordinator.get_value(PATH_HASCL):
        entities.append(
            AquariteValueSensorEntity(coordinator, "cl", "modules.cl.current")
        )
    if coordinator.get_value(PATH_HASPH):
        entities.append(
            AquariteValueSensorEntity(
                coordinator,
                "ph",
                "modules.ph.current",
                device_class=SensorDeviceClass.PH,
            )
        )
    if coordinator.get_value(PATH_HASRX):
        entities.append(
            AquariteRxValueSensorEntity(coordinator, "rx", "modules.rx.current")
        )
    if coordinator.get_value(PATH_HASUV):
        entities.append(
            AquariteValueSensorEntity(coordinator, "uv", "modules.uv.current")
        )
    if coordinator.get_value(PATH_HASHIDRO):
        is_electrolysis = coordinator.get_value("hidro.is_electrolysis")
        key = "electrolysis" if is_electrolysis else "hydrolysis"
        entities.append(
            AquariteHydrolyserSensorEntity(coordinator, key, "hidro.current")
        )

    # Wi-Fi signal strength (diagnostic, off by default)
    entities.append(AquariteRssiSensorEntity(coordinator))

    # Time and Interval Sensors
    entities.append(
        AquariteTimeSensorEntity(
            coordinator, "filtration_intel_time", "filtration.intel.time"
        )
    )

    # Location sensors (diagnostic, off by default)
    for translation_key, key in (
        ("city", "city"),
        ("street", "street"),
        ("zipcode", "zipcode"),
        ("country", "country"),
        ("latitude", "lat"),
        ("longitude", "lng"),
    ):
        entities.append(AquariteLocationSensorEntity(coordinator, translation_key, key))

    entities.append(AquaritePoolNameSensorEntity(coordinator))
    return entities


class AquariteTemperatureSensorEntity(AquariteEntity, SensorEntity):
    """Temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

    @property
    def native_value(self) -> float | None:
        """Return the temperature value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value)
        except TypeError, ValueError:
            return None


class AquariteValueSensorEntity(AquariteEntity, SensorEntity):
    """Generic value sensor entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        translation_key: str,
        value_path: str,
        device_class: SensorDeviceClass | None = None,
        native_unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize the value sensor."""
        super().__init__(coordinator)
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value) / 100
        except TypeError, ValueError:
            return None


class AquariteTimeSensorEntity(AquariteEntity, SensorEntity):
    """Time sensor entity."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the time sensor."""
        super().__init__(coordinator)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

    @property
    def native_value(self) -> float | None:
        """Return the time value in hours."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value) / 60
        except TypeError, ValueError:
            return None


class AquariteHydrolyserSensorEntity(AquariteEntity, SensorEntity):
    """Hydrolyser sensor entity."""

    _attr_native_unit_of_measurement = "g/h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the hydrolyser sensor."""
        super().__init__(coordinator)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

    @property
    def native_value(self) -> float | None:
        """Return the hydrolyser value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value) / 10
        except TypeError, ValueError:
            return None


class AquariteRxValueSensorEntity(AquariteEntity, SensorEntity):
    """Redox value sensor entity."""

    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the Rx sensor."""
        super().__init__(coordinator)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

    @property
    def native_value(self) -> int | None:
        """Return the Rx value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return int(value)
        except TypeError, ValueError:
            return None


class AquariteLocationSensorEntity(AquariteEntity, SensorEntity):
    """Location sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        translation_key: str,
        form_key: str,
    ) -> None:
        """Initialize the location sensor."""
        super().__init__(coordinator)
        self._form_key = form_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

    @property
    def native_value(self) -> str | None:
        """Return the location value."""
        form = self.coordinator.get_value("form")
        return form.get(self._form_key) if form else None


class AquaritePoolNameSensorEntity(AquariteEntity, SensorEntity):
    """Pool name sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AquariteDataUpdateCoordinator) -> None:
        """Initialize the pool name sensor."""
        super().__init__(coordinator)
        self._attr_translation_key = "pool_name"
        self._attr_unique_id = self.build_unique_id("pool_name")

    @property
    def native_value(self) -> str:
        """Return the pool name."""
        return self.coordinator.pool_name


class AquariteRssiSensorEntity(AquariteEntity, SensorEntity):
    """Controller Wi-Fi signal strength sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AquariteDataUpdateCoordinator) -> None:
        """Initialize the RSSI sensor."""
        super().__init__(coordinator)
        self._attr_translation_key = "rssi"
        self._attr_unique_id = self.build_unique_id("rssi")

    @property
    def native_value(self) -> int | None:
        """Return the RSSI value."""
        value = self.coordinator.get_value("main.RSSI")
        try:
            return int(value)
        except TypeError, ValueError:
            return None
