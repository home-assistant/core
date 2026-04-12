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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aquarite sensors."""
    dataservice = entry.runtime_data.coordinator
    pool_id = dataservice.pool_id
    pool_name = entry.title

    entities: list[AquariteEntity] = []

    # Pool water temperature (the only read-only temperature; all setpoints
    # are exposed as Number entities — see number.py)
    entities.append(
        AquariteTemperatureSensorEntity(
            dataservice, pool_id, pool_name,
            "Temperature", "temperature", "main.temperature",
        )
    )

    # Module Presence Sensors
    if dataservice.get_value(PATH_HASCD):
        entities.append(
            AquariteValueSensorEntity(
                dataservice, pool_id, pool_name, "CD", "cd", "modules.cd.current"
            )
        )

    if dataservice.get_value(PATH_HASCL):
        entities.append(
            AquariteValueSensorEntity(
                dataservice, pool_id, pool_name, "Cl", "cl", "modules.cl.current"
            )
        )

    if dataservice.get_value(PATH_HASPH):
        entities.append(
            AquariteValueSensorEntity(
                dataservice, pool_id, pool_name, "pH", "ph",
                "modules.ph.current",
                device_class=SensorDeviceClass.PH,
            )
        )

    if dataservice.get_value(PATH_HASRX):
        entities.append(
            AquariteRxValueSensorEntity(
                dataservice, pool_id, pool_name, "Rx", "rx", "modules.rx.current"
            )
        )

    if dataservice.get_value(PATH_HASUV):
        entities.append(
            AquariteValueSensorEntity(
                dataservice, pool_id, pool_name, "UV", "uv", "modules.uv.current"
            )
        )

    if dataservice.get_value(PATH_HASHIDRO):
        is_electrolysis = dataservice.get_value("hidro.is_electrolysis")
        name = "Electrolysis" if is_electrolysis else "Hidrolysis"
        key = "electrolysis" if is_electrolysis else "hydrolysis"
        entities.append(
            AquariteHydrolyserSensorEntity(
                dataservice, pool_id, pool_name, name, key, "hidro.current"
            )
        )

    # Wi-Fi signal strength (diagnostic, off by default — only useful on Wi-Fi controllers)
    entities.append(
        AquariteRssiSensorEntity(dataservice, pool_id, pool_name)
    )

    # Time and Interval Sensors
    entities.append(
        AquariteTimeSensorEntity(
            dataservice, pool_id, pool_name,
            "Filtration Intel Time", "filtration_intel_time",
            "filtration.intel.time",
            native_unit_of_measurement="h",
        )
    )

    # Location sensors (diagnostic)
    for name, translation_key, key in (
        ("City", "city", "city"),
        ("Street", "street", "street"),
        ("Zipcode", "zipcode", "zipcode"),
        ("Country", "country", "country"),
        ("Latitude", "latitude", "lat"),
        ("Longitude", "longitude", "lng"),
    ):
        entities.append(
            AquariteLocationSensorEntity(
                dataservice, pool_id, pool_name, name, translation_key, key
            )
        )

    entities.append(
        AquaritePoolNameSensorEntity(dataservice, pool_id, pool_name)
    )

    async_add_entities(entities)


class AquariteTemperatureSensorEntity(AquariteEntity, SensorEntity):
    """Temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return the temperature value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class AquariteValueSensorEntity(AquariteEntity, SensorEntity):
    """Generic value sensor entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
        device_class: SensorDeviceClass | None = None,
        native_unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize the value sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value) / 100
        except (TypeError, ValueError):
            return None


class AquariteTimeSensorEntity(AquariteEntity, SensorEntity):
    """Time sensor entity."""

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
        device_class: SensorDeviceClass | None = None,
        native_unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize the time sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return the time value in hours."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value) / 60
        except (TypeError, ValueError):
            return None


class AquariteHydrolyserSensorEntity(AquariteEntity, SensorEntity):
    """Hydrolyser sensor entity."""

    _attr_native_unit_of_measurement = "gr/h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the hydrolyser sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> float | None:
        """Return the hydrolyser value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return float(value) / 10
        except (TypeError, ValueError):
            return None


class AquariteRxValueSensorEntity(AquariteEntity, SensorEntity):
    """Redox value sensor entity."""

    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the Rx sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> int | None:
        """Return the Rx value."""
        value = self.coordinator.get_value(self._value_path)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class AquariteLocationSensorEntity(AquariteEntity, SensorEntity):
    """Location sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        name: str,
        translation_key: str,
        form_key: str,
    ) -> None:
        """Initialize the location sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._form_key = form_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(name)

    @property
    def native_value(self) -> str | None:
        """Return the location value."""
        form = self.coordinator.get_value("form")
        return form.get(self._form_key) if form else None


class AquaritePoolNameSensorEntity(AquariteEntity, SensorEntity):
    """Pool name sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the pool name sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._attr_translation_key = "pool_name"
        self._attr_unique_id = self.build_unique_id("name")

    @property
    def native_value(self) -> str:
        """Return the pool name."""
        return self._pool_name


class AquariteRssiSensorEntity(AquariteEntity, SensorEntity):
    """Controller Wi-Fi signal strength sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the RSSI sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._attr_translation_key = "rssi"
        self._attr_unique_id = self.build_unique_id("RSSI")

    @property
    def native_value(self) -> int | None:
        """Return the RSSI value."""
        value = self.coordinator.get_value("main.RSSI")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
