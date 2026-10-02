"""Support for Daikin AC sensors."""

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SENSOR_PERIOD_MONTHLY,
    SENSOR_PERIOD_WEEKLY,
    SENSOR_PERIOD_YEARLY,
    SENSOR_PERIODS,
)
from .device import DaikinOnectaDevice
from .entity_descriptions import SENSOR_DESCRIPTIONS, SENSOR_MODEL_ATTRIBUTES

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

    from .coordinator import OnectaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnergySensorDetails:
    """Parameters that identify an energy sensor."""

    embedded_id: str
    management_point_type: str
    sensor_type: str
    operation_mode: str
    period: str
    datatype: str


@dataclass(frozen=True)
class ValueSensorDetails:
    """Parameters that identify a value sensor."""

    embedded_id: str
    management_point_type: str
    sub_type: str | None
    value: str


@dataclass(frozen=True)
class EnergySourceDetails:
    """Energy source metadata used while creating sensors."""

    sensor_type: str
    source: object
    datatype: str


async def async_setup(hass: HomeAssistant, async_add_entities) -> None:
    """Old way of setting up the Daikin sensors.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


def handle_energy_sensors(
    coordinator,
    device,
    management_point,
    source_details: EnergySourceDetails,
    sensors,
):
    """Add energy sensors for the periods exposed by an energy source."""
    for mode in ("heating", "cooling"):
        series = getattr(source_details.source, mode)
        if series is None:
            continue
        periods = {
            "d": series.day,
            "w": series.week,
            "m": series.month,
        }
        for period, values in periods.items():
            if values is None:
                continue
            if period == SENSOR_PERIOD_YEARLY:
                sensors.append(
                    DaikinEnergySensor(
                        device,
                        coordinator,
                        EnergySensorDetails(
                            management_point.embedded_id,
                            management_point.management_point_type,
                            source_details.sensor_type,
                            mode,
                            SENSOR_PERIOD_MONTHLY,
                            source_details.datatype,
                        ),
                    )
                )
            if period in SENSOR_PERIODS:
                sensors.append(
                    DaikinEnergySensor(
                        device,
                        coordinator,
                        EnergySensorDetails(
                            management_point.embedded_id,
                            management_point.management_point_type,
                            source_details.sensor_type,
                            mode,
                            period,
                            source_details.datatype,
                        ),
                    )
                )


def add_simple_sensors(coordinator, device, management_point, sensors) -> None:
    """Add sensors for simple characteristics of one management point."""
    supported_management_point_types = {
        "domesticHotWaterTank",
        "domesticHotWaterFlowThrough",
        "climateControl",
        "climateControlMainZone",
    }
    for value, characteristic in management_point.simple_characteristics().items():
        if value not in SENSOR_DESCRIPTIONS:
            continue
        values = characteristic.values or []
        if (
            characteristic.value is not None
            and characteristic.settable
            and "on" in values
            and "off" in values
        ):
            continue
        if not values and isinstance(characteristic.value, bool):
            continue
        if (
            value == "operationMode"
            and management_point.management_point_type
            in supported_management_point_types
        ):
            continue
        if characteristic.value is not None:
            sensors.append(
                DaikinValueSensor(
                    device,
                    coordinator,
                    ValueSensorDetails(
                        management_point.embedded_id,
                        management_point.management_point_type,
                        None,
                        value,
                    ),
                )
            )


def add_sensory_sensors(coordinator, device, management_point, sensors) -> None:
    """Add sensors for sensory data exposed by one management point."""
    if management_point.sensory_data is None:
        return
    sensory_data = management_point.sensory_data.value
    sensors.extend(
        DaikinValueSensor(
            device,
            coordinator,
            ValueSensorDetails(
                management_point.embedded_id,
                management_point.management_point_type,
                "sensoryData",
                sensor,
            ),
        )
        for sensor in (
            "roomTemperature",
            "outdoorTemperature",
            "leavingWaterTemperature",
            "tankTemperature",
            "roomHumidity",
            "pm1Concentration",
            "pm25Concentration",
            "pm10Concentration",
        )
        if sensor in SENSOR_DESCRIPTIONS
        and (attribute := SENSOR_MODEL_ATTRIBUTES.get(sensor)) is not None
        and getattr(sensory_data, attribute) is not None
    )


def add_management_point_sensors(
    coordinator, device, management_point, sensors
) -> None:
    """Add all sensors exposed by a management point."""
    add_simple_sensors(coordinator, device, management_point, sensors)
    add_sensory_sensors(coordinator, device, management_point, sensors)
    for datatype, energy_data in (
        ("consumption", management_point.consumption_data),
        ("output", management_point.output_data),
    ):
        if energy_data is None:
            continue
        for sensor_type in ("electrical", "gas", "thermal"):
            source = getattr(energy_data.value, sensor_type)
            if source is not None:
                handle_energy_sensors(
                    coordinator,
                    device,
                    management_point,
                    EnergySourceDetails(sensor_type, source, datatype),
                    sensors,
                )


def _legacy_value_sensor_id_migrations(device: DaikinOnectaDevice) -> dict[str, str]:
    """Return legacy-to-current value sensor IDs for a device."""
    migrations: dict[str, str] = {}
    for management_point in device.device.management_points:
        for value in SENSOR_DESCRIPTIONS:
            for sub_type in (None, "sensoryData"):
                old_unique_id = f"{device.id}_{management_point.management_point_type}_{sub_type}_{value}"
                migrations.setdefault(
                    old_unique_id,
                    f"{device.id}_{management_point.embedded_id}_{sub_type}_{value}",
                )
    return migrations


def _legacy_energy_sensor_id_migrations(device: DaikinOnectaDevice) -> dict[str, str]:
    """Return legacy-to-current energy sensor IDs for a device."""
    migrations: dict[str, str] = {}
    for management_point in device.device.management_points:
        for datatype in ("consumption", "output"):
            for sensor_type in ("electrical", "gas", "thermal"):
                for operation_mode in ("heating", "cooling"):
                    for period in SENSOR_PERIODS:
                        old_unique_id = f"{device.id}_{management_point.management_point_type}_{sensor_type}_{operation_mode}_{period}"
                        migrations.setdefault(
                            old_unique_id,
                            f"{device.id}_{management_point.embedded_id}_{sensor_type}_{operation_mode}_{period}_{datatype}",
                        )
    return migrations


def migrate_legacy_sensor_unique_ids(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    devices: dict[str, DaikinOnectaDevice],
) -> None:
    """Use embedded management-point IDs for existing sensor unique IDs.

    The previous IDs did not distinguish management points of the same type or
    energy consumption from output. Update registry entries before platforms
    are loaded so existing entity IDs, customizations, and history are kept.
    """
    entity_registry = er.async_get(hass)
    migrations: dict[str, str] = {}

    for device in devices.values():
        migrations.update(_legacy_value_sensor_id_migrations(device))
        migrations.update(_legacy_energy_sensor_id_migrations(device))

    for entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if entry.domain != "sensor" or entry.platform != DOMAIN:
            continue
        new_unique_id = migrations.get(entry.unique_id)
        if (
            new_unique_id is None
            or entity_registry.async_get_entity_id("sensor", DOMAIN, new_unique_id)
            is not None
        ):
            continue
        entity_registry.async_update_entity(
            entry.entity_id, new_unique_id=new_unique_id
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin sensors based on config_entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    sensors = []
    for device in (coordinator.data or {}).values():
        sensors.append(
            DaikinLimitSensor(hass, config_entry, device, coordinator, "remaining_day")
        )
        for management_point in device.device.management_points:
            add_management_point_sensors(coordinator, device, management_point, sensors)

    async_add_entities(sensors)


class DaikinEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a power/energy sensor."""

    def __init__(
        self, device: DaikinOnectaDevice, coordinator, details: EnergySensorDetails
    ) -> None:
        """Initialize an energy sensor for a management point."""
        super().__init__(coordinator)
        self._device = device
        self._management_point_type = details.management_point_type
        mpt = (
            details.management_point_type[0].upper() + details.management_point_type[1:]
        )
        assert self._device.ha_device_id is not None
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._device.id + details.embedded_id)},
            "name": self._device.name + " " + mpt,
            "via_device_id": self._device.ha_device_id,
        }
        self._device.fill_device_info(self._attr_device_info, details.embedded_id)
        self._embedded_id = details.embedded_id
        self._operation_mode = details.operation_mode
        self._attr_has_entity_name = True
        self._period = details.period
        self._datatype = details.datatype
        period_name = SENSOR_PERIODS[details.period]
        buildname = f"{details.operation_mode.capitalize()}{period_name}{details.sensor_type.capitalize()}{details.datatype.capitalize()}"
        self.entity_description = SENSOR_DESCRIPTIONS[buildname]
        self._sensor_type = details.sensor_type
        self._attr_unique_id = f"{self._device.id}_{details.embedded_id}_{details.sensor_type}_{self._operation_mode}_{self._period}_{self._datatype}"
        self.update_state()
        _LOGGER.info(
            "Device '%s:%s' supports sensor '%s'",
            device.name,
            self._embedded_id,
            buildname,
        )

    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        self._attr_native_value = self.sensor_value()

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return super().available and self._device.available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    def sensor_value(self):
        """Return energy aggregated for the current day, week, month, or year.

        Daikin returns rolling windows for each aggregation period. The first
        half of the daily, weekly, and yearly arrays represents the preceding
        period; the second half represents the current period. Consequently,
        the current day starts at ``d[12]``, the current week at ``w[7]``,
        and the current year at ``m[12]``. The current month is a single slot
        in the monthly array.

        Daikin publishes consumption data on its own schedule. ``None`` means
        that a time slot is not available yet and contributes no consumption
        until a later update supplies its value.
        """
        point = self._device.management_point(self._embedded_id)
        if point is None:
            return None
        energy = (
            point.consumption_data
            if self._datatype == "consumption"
            else point.output_data
        )
        if energy is None:
            return None
        source = getattr(energy.value, self._sensor_type)
        if source is None:
            return None
        series = getattr(source, self._operation_mode)
        if series is None:
            return None
        period_data = {
            "d": series.day,
            "w": series.week,
            "m": series.month,
            SENSOR_PERIOD_MONTHLY: series.month,
        }.get(self._period)
        if period_data is None:
            return None

        # Treat not-yet-published time slots as zero until Daikin provides the
        # corresponding consumption value in a later coordinator update.
        energy_values = [0 if value is None else value for value in period_data]
        if self._period == SENSOR_PERIOD_WEEKLY:
            # w[0:7] is last week; w[7:14] is this week.
            start_index = 7
            end_index = len(energy_values)
        elif self._period == SENSOR_PERIOD_MONTHLY:
            # m[12] is January of this year, so select this calendar month.
            start_index = 11 + dt_util.now().month
            end_index = start_index + 1
        else:
            # d[0:12] and m[0:12] are the preceding day/year respectively.
            start_index = 12
            end_index = len(energy_values)
        return round(sum(energy_values[start_index:end_index]), 3)


class DaikinValueSensor(CoordinatorEntity, SensorEntity):
    """Represent a Daikin characteristic or sensory-data value."""

    def __init__(
        self, device: DaikinOnectaDevice, coordinator, details: ValueSensorDetails
    ) -> None:
        """Initialize the sensor from a device value."""
        _LOGGER.info(
            "DaikinValueSensor '%s' '%s' '%s'",
            details.management_point_type,
            details.sub_type,
            details.value,
        )
        super().__init__(coordinator)
        self._device = device
        self._management_point_type = details.management_point_type
        mpt = (
            details.management_point_type[0].upper() + details.management_point_type[1:]
        )
        assert self._device.ha_device_id is not None
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._device.id + details.embedded_id)},
            "name": self._device.name + " " + mpt,
            "via_device_id": self._device.ha_device_id,
        }
        self._device.fill_device_info(self._attr_device_info, details.embedded_id)
        self._embedded_id = details.embedded_id
        self._sub_type = details.sub_type
        self._value = details.value
        self._attr_has_entity_name = True
        self.entity_description = SENSOR_DESCRIPTIONS[details.value]
        self._attr_unique_id = (
            f"{self._device.id}_{details.embedded_id}_{self._sub_type}_{self._value}"
        )
        self.update_state()
        _LOGGER.info(
            "Device '%s:%s' supports sensor '%s'",
            device.name,
            self._embedded_id,
            self._value,
        )

    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        self._attr_native_value = self.sensor_value()

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return super().available and self._device.available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    def sensor_value(self):
        """Return a typed characteristic or sensory value."""
        point = self._device.management_point(self._embedded_id)
        if point is None:
            return None
        if self._sub_type == "sensoryData":
            sensory_data = point.sensory_data
            if sensory_data is None:
                return None
            attribute = SENSOR_MODEL_ATTRIBUTES.get(self._value)
            characteristic = (
                getattr(sensory_data.value, attribute)
                if attribute is not None
                else None
            )
        else:
            characteristic = point.characteristic(self._value)
        result = characteristic.value if characteristic is not None else None
        _LOGGER.debug(
            "Device '%s' sensor '%s' value '%s'", self._device.name, self._value, result
        )
        return result


class DaikinLimitSensor(CoordinatorEntity, SensorEntity):
    """Represent a Daikin API rate-limit value."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: DaikinOnectaDevice,
        coordinator,
        limit_key,
    ) -> None:
        """Initialize a rate-limit sensor."""
        _LOGGER.info("Device '%s' LimitSensor '%s'", device.name, limit_key)
        super().__init__(coordinator)
        self._hass = hass
        self._config_entry = config_entry
        self._device = device
        self._limit_key = limit_key
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self._device.id}_limitsensor_{self._limit_key}"
        assert self._device.ha_device_id is not None
        self.entity_description = SENSOR_DESCRIPTIONS["RatelimitRemainingDay"]
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._device.id + "gateway")},
            "name": self._device.name + " " + "Gateway",
            "via_device_id": self._device.ha_device_id,
        }
        self._device.fill_device_info(self._attr_device_info, "gateway")
        self.update_state()
        _LOGGER.info(
            "Device '%s' supports sensor '%s'",
            device.name,
            self._limit_key,
        )

    def update_state(self) -> None:
        """Refresh the rate-limit value."""
        self._attr_native_value = self.sensor_value()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    def sensor_value(self):
        """Return the current API rate-limit value."""
        daikin_api = self._config_entry.runtime_data.api
        return daikin_api.rate_limits[self._limit_key]
