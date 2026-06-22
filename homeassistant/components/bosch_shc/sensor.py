"""Platform for sensor integration."""

from __future__ import annotations

from boschshcpy import SHCSession
from boschshcpy.device import SHCDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_SESSION, DOMAIN, LOGGER, OPT_DIAGNOSTIC_ENTITIES
from .entity import SHCEntity, async_migrate_to_new_unique_id, device_excluded

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SHC sensor platform."""
    entities: list[SensorEntity] = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]
    sensor: SHCDevice
    diagnostic_enabled = config_entry.options.get(OPT_DIAGNOSTIC_ENTITIES, True)

    for sensor in session.device_helper.thermostats:
        if device_excluded(sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.SENSOR, device=sensor, attr_name="Temperature"
        )
        entities.append(
            TemperatureSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        if diagnostic_enabled:
            await async_migrate_to_new_unique_id(
                hass, Platform.SENSOR, device=sensor, attr_name="Valvetappet"
            )
            entities.append(
                ValveTappetSensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )

    for sensor in (
        session.device_helper.wallthermostats + session.device_helper.roomthermostats
    ):
        if device_excluded(sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.SENSOR, device=sensor, attr_name="Temperature"
        )
        entities.append(
            TemperatureSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass, Platform.SENSOR, device=sensor, attr_name="Humidity"
        )
        if getattr(sensor, "supports_humidity", True):
            entities.append(
                HumiditySensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )
        # #198 / #330: Room Thermostat II 230V with an external floor sensor
        # wired to its terminal exposes a second temperature via
        # TerminalConfiguration — surface it as a dedicated sensor. Only when a
        # sensor is actually connected (terminal_temperature is not None).
        if getattr(sensor, "terminal_temperature", None) is not None:
            entities.append(
                TerminalTemperatureSensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )

    for sensor in session.device_helper.twinguards:
        if device_excluded(sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.SENSOR, device=sensor, attr_name="Temperature"
        )
        entities.append(
            TemperatureSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass, Platform.SENSOR, device=sensor, attr_name="Humidity"
        )
        if getattr(sensor, "supports_humidity", True):
            entities.append(
                HumiditySensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )
        await async_migrate_to_new_unique_id(
            hass, Platform.SENSOR, device=sensor, attr_name="Purity"
        )
        entities.append(
            PuritySensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass, Platform.SENSOR, device=sensor, attr_name="AirQuality"
        )
        entities.append(
            AirQualitySensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass,
            Platform.SENSOR,
            device=sensor,
            attr_name="TemperatureRating",
            old_unique_id=f"{sensor.serial}_temperature_rating",
        )
        entities.append(
            TemperatureRatingSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass,
            Platform.SENSOR,
            device=sensor,
            attr_name="HumidityRating",
            old_unique_id=f"{sensor.serial}_humidity_rating",
        )
        entities.append(
            HumidityRatingSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass,
            Platform.SENSOR,
            device=sensor,
            attr_name="PurityRating",
            old_unique_id=f"{sensor.serial}_purity_rating",
        )
        entities.append(
            PurityRatingSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        if diagnostic_enabled:
            entities.append(
                TwinguardCombinedRatingSensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )
            entities.append(
                TwinguardDescriptionSensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )

    for sensor in (
        session.device_helper.smart_plugs
        + session.device_helper.light_switches_bsm
        + session.device_helper.micromodule_light_controls
        + session.device_helper.micromodule_shutter_controls
        + session.device_helper.micromodule_blinds
    ):
        if device_excluded(sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass,
            Platform.SENSOR,
            device=sensor,
            attr_name="Power",
            old_unique_id=f"{sensor.serial}_power",
        )
        entities.append(
            PowerSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass,
            Platform.SENSOR,
            device=sensor,
            attr_name="Energy",
            old_unique_id=f"{sensor.serial}_energy",
        )
        entities.append(
            EnergySensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        # #331: Smart Plug [+M] in Mini-PV mode reports PV yield separately.
        if getattr(sensor, "supports_energy_yield", False):
            entities.append(
                EnergyYieldSensor(device=sensor, entry_id=config_entry.entry_id)
            )
            entities.append(
                PowerYieldSensor(device=sensor, entry_id=config_entry.entry_id)
            )

    for sensor in session.device_helper.smart_plugs_compact:
        if device_excluded(sensor, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass,
            Platform.SENSOR,
            device=sensor,
            attr_name="Power",
            old_unique_id=f"{sensor.serial}_power",
        )
        entities.append(
            PowerSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass,
            Platform.SENSOR,
            device=sensor,
            attr_name="Energy",
            old_unique_id=f"{sensor.serial}_energy",
        )
        entities.append(
            EnergySensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        if getattr(sensor, "supports_energy_yield", False):
            entities.append(
                EnergyYieldSensor(device=sensor, entry_id=config_entry.entry_id)
            )
            entities.append(
                PowerYieldSensor(device=sensor, entry_id=config_entry.entry_id)
            )
        if diagnostic_enabled:
            await async_migrate_to_new_unique_id(
                hass,
                Platform.SENSOR,
                device=sensor,
                attr_name="CommunicationQuality",
                old_unique_id=f"{sensor.serial}_communication_quality",
            )
            entities.append(
                CommunicationQualitySensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )

    for sensor in session.device_helper.motion_detectors:
        if device_excluded(sensor, config_entry.options):
            continue
        entities.append(
            IlluminanceLevelSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )

    for sensor in session.device_helper.motion_detectors2:
        if device_excluded(sensor, config_entry.options):
            continue
        entities.append(
            IlluminanceLevelSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        await async_migrate_to_new_unique_id(
            hass,
            Platform.SENSOR,
            device=sensor,
            attr_name="Temperature",
        )
        entities.append(
            TemperatureSensor(
                device=sensor,
                entry_id=config_entry.entry_id,
            )
        )
        # WalkTest state sensor: only created when WalkTest service is present.
        if getattr(sensor, "supports_walk_test", False) and sensor.walk_state is not None:
            entities.append(
                WalkStateSensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )
        # DetectionTest state sensor: the local-API counterpart of WalkTest.
        if getattr(sensor, "supports_detection_test", False):
            entities.append(
                DetectionStateSensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )
        # Installation profile (e.g. GENERIC / OUTDOOR) — read-only: the
        # write path is an undocumented device-level call, so only the
        # current selection is surfaced for now.
        if getattr(sensor, "supported_profiles", None):
            entities.append(
                InstallationProfileSensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )
        if diagnostic_enabled:
            await async_migrate_to_new_unique_id(
                hass,
                Platform.SENSOR,
                device=sensor,
                attr_name="CommunicationQuality",
            )
            entities.append(
                CommunicationQualitySensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )

    if diagnostic_enabled:
        for sensor in session.device_helper.shutter_contacts2:
            if device_excluded(sensor, config_entry.options):
                continue
            if not hasattr(sensor, "communicationquality"):
                continue
            await async_migrate_to_new_unique_id(
                hass,
                Platform.SENSOR,
                device=sensor,
                attr_name="CommunicationQuality",
            )
            entities.append(
                CommunicationQualitySensor(
                    device=sensor,
                    entry_id=config_entry.entry_id,
                )
            )

    sensor = session.emma
    entities.append(
        EmmaPowerSensor(
            device=sensor,
            entry_id=config_entry.entry_id,
        )
    )

    if diagnostic_enabled:
        for sensor in (
            session.device_helper.motion_detectors
            + session.device_helper.motion_detectors2
            + session.device_helper.shutter_contacts
            + session.device_helper.shutter_contacts2
            + session.device_helper.smoke_detectors
            + session.device_helper.thermostats
            + session.device_helper.twinguards
            + session.device_helper.universal_switches
            + session.device_helper.wallthermostats
            + session.device_helper.roomthermostats
            + session.device_helper.water_leakage_detectors
        ):
            if device_excluded(sensor, config_entry.options):
                continue
            if sensor.supports_batterylevel:
                entities.append(
                    BatteryLevelSensor(
                        device=sensor,
                        entry_id=config_entry.entry_id,
                    )
                )

    if entities:
        async_add_entities(entities)


class TemperatureSensor(SHCEntity, SensorEntity):
    """Representation of an SHC temperature reporting sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC temperature reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Temperature"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_temperature"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.temperature


class TerminalTemperatureSensor(SHCEntity, SensorEntity):
    """External floor/terminal sensor temperature of a Room Thermostat II 230V.

    #198 / #330: RTH2_230 with a floor sensor wired to its terminal reports a
    second temperature via TerminalConfiguration (distinct from the room
    TemperatureLevel). Only created when a sensor is actually connected.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the terminal (floor) temperature sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Floor Temperature"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_terminal_temperature"
        )

    @property
    def native_value(self):
        """Return the external floor/terminal sensor temperature."""
        return self._device.terminal_temperature


class HumiditySensor(SHCEntity, SensorEntity):
    """Representation of an SHC humidity reporting sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC humidity reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Humidity"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_humidity"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.humidity


class PuritySensor(SHCEntity, SensorEntity):
    """Representation of an SHC purity reporting sensor."""

    # Bosch "purity" is an air-purity/VOC ppm value, NOT CO2.  HA Core's own
    # bosch_shc integration assigns no device_class here either; the previous
    # SensorDeviceClass.CO2 mis-classified the reading (and pulled in HA's CO2
    # safety thresholds / statistics handling). #204
    _attr_icon = "mdi:air-filter"
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC purity reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Purity"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_purity"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.purity


class AirQualitySensor(SHCEntity, SensorEntity):
    """Representation of an SHC airquality reporting sensor."""

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC airquality reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Air Quality"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_airquality"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            return self._device.combined_rating.name
        except ValueError as err:
            LOGGER.warning("Unknown combined rating for %s: %s", self._device.name, err)
            return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes.

        comfort_zone is read from the AirQualityLevelService via a service-level
        accessor (_airqualitylevel_service.comfortZone). The SHCTwinguard model
        does not expose a model-level comfort_zone property, so we access the
        underlying service directly and fall back to None when unavailable.
        """
        comfort_zone = None
        try:
            service = getattr(self._device, "_airqualitylevel_service", None)
            if service is not None:
                comfort_zone = service.comfortZone
        except (AttributeError, KeyError):
            pass
        attrs = {
            "rating_description": self._device.description,
        }
        if comfort_zone is not None:
            attrs["comfort_zone"] = comfort_zone
        return attrs


class TemperatureRatingSensor(SHCEntity, SensorEntity):
    """Representation of an SHC temperature rating sensor."""

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC temperature rating sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Temperature Rating"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_temperaturerating"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            return self._device.temperature_rating.name
        except ValueError as err:
            LOGGER.warning(
                "Unknown temperature rating for %s: %s", self._device.name, err
            )
            return None


class CommunicationQualitySensor(SHCEntity, SensorEntity):
    """Representation of an SHC communication quality reporting sensor."""

    _attr_icon = "mdi:wifi"

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC communication quality reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Communication Quality"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_communicationquality"
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            return self._device.communicationquality.name
        except (ValueError, AttributeError) as err:
            LOGGER.warning(
                "Unknown communication quality for %s: %s", self._device.name, err
            )
            return None


class HumidityRatingSensor(SHCEntity, SensorEntity):
    """Representation of an SHC humidity rating sensor."""

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC humidity rating sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Humidity Rating"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_humidityrating"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            return self._device.humidity_rating.name
        except ValueError as err:
            LOGGER.warning(
                "Unknown humidity rating for %s: %s", self._device.name, err
            )
            return None


class PurityRatingSensor(SHCEntity, SensorEntity):
    """Representation of an SHC purity rating sensor."""

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC purity rating sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Purity Rating"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_purityrating"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            return self._device.purity_rating.name
        except ValueError as err:
            LOGGER.warning(
                "Unknown purity rating for %s: %s", self._device.name, err
            )
            return None


class PowerSensor(SHCEntity, SensorEntity):
    """Representation of an SHC power reporting sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC power reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Power"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_power"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.powerconsumption


class EmmaPowerSensor(SHCEntity, SensorEntity):
    """Representation of an SHC power reporting sensor."""

    from boschshcpy import SHCEmma

    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, device: SHCEmma, entry_id: str) -> None:
        """Initialize an SHC power reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Power"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_power"

    async def async_added_to_hass(self):
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def update_entity_information():
            self.schedule_update_ha_state()

        self._device.subscribe_callback(self.entity_id, update_entity_information)

    async def async_will_remove_from_hass(self):
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        self._device.unsubscribe_callback(self.entity_id)

    @property
    def native_value(self):
        """Return the state of the sensor. Negative value if power is consumed from the grid, positive if fed to the grid."""
        return self._device.value

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "power_flow": self._device.localizedSubtitles,
        }


class EnergySensor(SHCEntity, SensorEntity):
    """Representation of an SHC energy reporting sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC energy reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Energy"
        self._attr_unique_id = f"{device.root_device_id}_{self._device.id}_energy"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.energyconsumption / 1000.0


class EnergyYieldSensor(SHCEntity, SensorEntity):
    """PV energy yield of a Smart Plug [+M] in Mini-PV mode (#331)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the energy yield sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Energy Yield"
        self._attr_unique_id = (
            f"{device.root_device_id}_{self._device.id}_energy_yield"
        )

    @property
    def native_value(self):
        """Return the PV energy yield (kWh), or None when unreported."""
        value = self._device.energy_yield
        return None if value is None else value / 1000.0


class PowerYieldSensor(SHCEntity, SensorEntity):
    """PV power yield of a Smart Plug [+M] as a positive value (#331).

    The PowerMeter reports negative powerConsumption while feeding in. This
    sensor exposes that production as a positive number (0 W while consuming),
    so it can be added directly to the HA Energy dashboard.
    """

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the power yield sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Power Yield"
        self._attr_unique_id = (
            f"{device.root_device_id}_{self._device.id}_power_yield"
        )

    @property
    def native_value(self):
        """Return positive PV power (W); 0 while net-consuming."""
        consumption = self._device.powerconsumption
        if consumption is None:
            return None
        return -consumption if consumption < 0 else 0.0


class ValveTappetSensor(SHCEntity, SensorEntity):
    """Representation of an SHC valve tappet reporting sensor."""

    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 0

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC valve tappet reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Valve Tappet"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_valvetappet"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.position

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        try:
            valve_tappet_state = self._device.valvestate.name
        except ValueError as err:
            LOGGER.warning(
                "Unknown valve tappet state for %s: %s", self._device.name, err
            )
            valve_tappet_state = None
        return {
            "valve_tappet_state": valve_tappet_state,
        }


class IlluminanceLevelSensor(SHCEntity, SensorEntity):
    """Representation of an SHC illuminance level reporting sensor.

    The Bosch SHC API spec defines illuminance as integer for both Gen1
    (SHCMotionDetector, model "MD") and Gen2 (SHCMotionDetector2, model "MD2").
    Gen1 devices report numeric lux values too (e.g. 13, 9, 22) — see #315.

    Metadata (state_class/device_class/unit) is STATIC so it never flip-flops:
    a previous conditional implementation dropped state_class whenever the
    value was momentarily None (offline / between polls), which re-raised the
    very state_class_removed repair this restores (and emitted "unit changed"
    warnings). Instead the metadata stays put and native_value coerces any
    non-numeric/qualitative value to None, so a hypothetical string-reporting
    firmware degrades to "unknown" rather than conflicting with MEASUREMENT.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_suggested_display_precision = 0

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize an SHC illuminance level reporting sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Illuminance"
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_illuminance"

    @property
    def native_value(self):
        """Return the numeric lux value, or None for non-numeric values."""
        value = self._device.illuminance
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        return None


class BatteryLevelSensor(SHCEntity, SensorEntity):
    """Granular battery-level diagnostic sensor (ENUM, all 5 BatteryLevelService states).

    Complements the binary BatterySensor (binary_sensor.py) which only signals
    OK vs. not-OK.  This sensor exposes the raw enum value so automations can
    distinguish LOW_BATTERY from CRITICALLY_LOW_BATTERY.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = [
        "OK",
        "LOW_BATTERY",
        "CRITICAL_LOW",
        "CRITICALLY_LOW_BATTERY",
        "NOT_AVAILABLE",
    ]

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize a battery-level sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Battery Level"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_battery_level"
        )

    @property
    def native_value(self):
        """Return the battery level state string, or None on unknown value."""
        try:
            return self._device.batterylevel.value
        except (ValueError, AttributeError) as err:
            LOGGER.warning(
                "Unknown battery level for %s: %s", self._device.name, err
            )
            return None


class TwinguardCombinedRatingSensor(SHCEntity, SensorEntity):
    """Diagnostic ENUM sensor for Twinguard overall combined air-quality rating.

    Surfaces the combinedRating field from AirQualityLevelService (CAT-3e gap).
    Distinct from AirQualitySensor which exposes the same value as its primary
    state — this entity is diagnostic-only so it does not clutter the default
    device view.  net-new unique_id suffix _combined_rating; no migration needed.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = ["GOOD", "MEDIUM", "BAD"]

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize a Twinguard combined-rating diagnostic sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Combined Rating"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_combined_rating"
        )

    @property
    def native_value(self):
        """Return the combined rating enum name, or None on unknown value."""
        try:
            return self._device.combined_rating.name
        except (ValueError, AttributeError) as err:
            LOGGER.warning(
                "Unknown combined rating for %s: %s", self._device.name, err
            )
            return None


class TwinguardDescriptionSensor(SHCEntity, SensorEntity):
    """Diagnostic sensor for Twinguard air-quality text description.

    Surfaces the description field from AirQualityLevelService (CAT-3e gap).
    net-new unique_id suffix _description; no migration needed.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize a Twinguard air-quality description diagnostic sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Air Quality Description"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_description"
        )

    @property
    def native_value(self):
        """Return the air quality description string."""
        return self._device.description


class WalkStateSensor(SHCEntity, SensorEntity):
    """Sensor for the Motion Detector II walk-test state.

    Reports the current WalkTest walkState enum name (WALK_TEST_STARTED /
    STOPPED / UNKNOWN).  The WalkTest service is optional on MD2 hardware;
    this sensor is only created when walk_state is not None.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["WALK_TEST_STARTED", "WALK_TEST_STOPPED", "UNKNOWN"]

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the walk-state sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Walk Test State"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_walk_state"
        )

    @property
    def native_value(self) -> str | None:
        """Return the current walk state as its enum name."""
        try:
            val = self._device.walk_state
            if val is None:
                return None
            return val.name
        except (AttributeError, ValueError):
            return None


class DetectionStateSensor(SHCEntity, SensorEntity):
    """Sensor for the Motion Detector II detection-test state.

    Reports the DetectionTest detectionState enum name (DETECTION_TEST_STARTED
    / STOPPED / UNKNOWN). The DetectionTest service is the local-API equivalent
    of the APK WalkTest service; created only when the device carries it.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        "DETECTION_TEST_STARTED",
        "DETECTION_TEST_STOPPED",
        "DETECTION_TEST_UNKNOWN",
    ]

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the detection-state sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Detection Test State"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_detection_state"
        )

    @property
    def native_value(self) -> str | None:
        """Return the current detection-test state as its enum name."""
        try:
            val = self._device.detection_state
            if val is None:
                return None
            return val.name
        except (AttributeError, ValueError):
            return None


class InstallationProfileSensor(SHCEntity, SensorEntity):
    """Read-only sensor for the device installation profile.

    Reports the currently selected installation environment (e.g. GENERIC /
    OUTDOOR). Read-only: the Bosch app can change this, but the local-API
    write path is undocumented, so only the current value is exposed.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the installation-profile sensor."""
        super().__init__(device, entry_id)
        self._attr_name = "Installation Profile"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_installation_profile"
        )
        # Options come from the device's advertised supportedProfiles.
        self._attr_options = list(getattr(device, "supported_profiles", []) or [])

    @property
    def native_value(self) -> str | None:
        """Return the current installation profile.

        Guarded: a profile not advertised in supported_profiles (e.g. after a
        firmware vocabulary change) would otherwise trip HA's ENUM "invalid
        value" validation on every update — return None (unknown) instead.
        """
        val = getattr(self._device, "profile", None)
        if val is None or val not in (self._attr_options or []):
            return None
        return val
