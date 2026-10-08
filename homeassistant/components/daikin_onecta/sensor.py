"""Support for Daikin AC sensors."""

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SENSOR_PERIOD_DAILY,
    SENSOR_PERIOD_MONTHLY,
    SENSOR_PERIOD_UNIQUE_IDS,
    SENSOR_PERIOD_WEEKLY,
    SENSOR_PERIOD_YEARLY,
    SENSOR_PERIODS,
)
from .device import DaikinOnectaDevice
from .entity import DaikinEntity
from .entity_descriptions import SENSOR_DESCRIPTIONS

if TYPE_CHECKING:
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


async def async_setup(hass, async_add_entities):
    """Old way of setting up the Daikin sensors.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


def add_energy_sensors(coordinator, device, management_point, sensors) -> None:
    """Add sensors for every typed energy aggregate exposed by a point."""
    periods = {
        "day": SENSOR_PERIOD_DAILY,
        "week": SENSOR_PERIOD_WEEKLY,
        "month": SENSOR_PERIOD_MONTHLY,
        "year": SENSOR_PERIOD_YEARLY,
    }
    order = {"day": 0, "week": 1, "year": 2, "month": 3}
    for aggregate in sorted(
        management_point.energy_aggregates,
        key=lambda aggregate: order[aggregate.period],
    ):
        sensors.append(
            DaikinEnergySensor(
                device,
                coordinator,
                EnergySensorDetails(
                    management_point.embedded_id,
                    management_point.management_point_type,
                    aggregate.source,
                    aggregate.operation_mode,
                    periods[aggregate.period],
                    aggregate.data_type,
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
    for value, characteristic in management_point.scalar_characteristics().items():
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
        and management_point.sensory_characteristic(sensor) is not None
    )


def add_management_point_sensors(
    coordinator, device, management_point, sensors
) -> None:
    """Add all sensors exposed by a management point."""
    add_simple_sensors(coordinator, device, management_point, sensors)
    add_sensory_sensors(coordinator, device, management_point, sensors)
    add_energy_sensors(coordinator, device, management_point, sensors)


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
    """Return older energy sensor unique IDs mapped to current IDs."""
    migrations: dict[str, str] = {}
    for management_point in device.device.management_points:
        for datatype in ("consumption", "output"):
            for sensor_type in ("electrical", "gas", "thermal"):
                for operation_mode in ("heating", "cooling"):
                    for period in SENSOR_PERIODS:
                        details = EnergySensorDetails(
                            management_point.embedded_id,
                            management_point.management_point_type,
                            sensor_type,
                            operation_mode,
                            period,
                            datatype,
                        )
                        old_unique_id = f"{device.id}_{management_point.management_point_type}_{sensor_type}_{operation_mode}_{period}"
                        migrations.setdefault(
                            old_unique_id, _energy_sensor_unique_id(device.id, details)
                        )
                        old_current_unique_id = f"{device.id}_{management_point.embedded_id}_{sensor_type}_{operation_mode}_{period}_{datatype}"
                        migrations[old_current_unique_id] = _energy_sensor_unique_id(
                            device.id, details
                        )
    return migrations


def _energy_sensor_unique_id(device_id: str, details: EnergySensorDetails) -> str:
    """Return the stable unique ID for an energy aggregate."""
    return (
        f"{device_id}_{details.embedded_id}_{details.sensor_type}_{details.operation_mode}_"
        f"{SENSOR_PERIOD_UNIQUE_IDS[details.period]}_{details.datatype}"
    )


def migrate_legacy_sensor_unique_ids(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    devices: dict[str, DaikinOnectaDevice],
) -> None:
    """Migrate existing sensor unique IDs without replacing registry entries.

    The previous IDs did not distinguish management points of the same type or
    energy consumption from output. The former energy IDs also used API period
    tokens, including ``m`` for yearly data. Update registry entries before
    platforms are loaded so entity IDs, customizations, and history are kept.
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


class DaikinEnergySensor(DaikinEntity, SensorEntity):
    """Representation of a power/energy sensor."""

    def __init__(
        self, device: DaikinOnectaDevice, coordinator, details: EnergySensorDetails
    ) -> None:
        """Initialize an energy sensor for a management point."""
        super().__init__(
            device, coordinator, details.embedded_id, details.management_point_type
        )
        self._management_point_type = details.management_point_type
        self._operation_mode = details.operation_mode
        self._attr_has_entity_name = True
        self._period = details.period
        self._datatype = details.datatype
        period_name = SENSOR_PERIODS[details.period]
        buildname = f"{details.operation_mode.capitalize()}{period_name}{details.sensor_type.capitalize()}{details.datatype.capitalize()}"
        self.entity_description = SENSOR_DESCRIPTIONS[buildname]
        self._sensor_type = details.sensor_type
        self._attr_unique_id = _energy_sensor_unique_id(self._device.id, details)
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
        period = {
            SENSOR_PERIOD_DAILY: "day",
            SENSOR_PERIOD_WEEKLY: "week",
            SENSOR_PERIOD_YEARLY: "year",
            SENSOR_PERIOD_MONTHLY: "month",
        }[self._period]
        aggregate = next(
            (
                aggregate
                for aggregate in point.energy_aggregates
                if aggregate.data_type == self._datatype
                and aggregate.source == self._sensor_type
                and aggregate.operation_mode == self._operation_mode
                and aggregate.period == period
            ),
            None,
        )
        if aggregate is None:
            return None
        return aggregate.current_total(
            month=dt_util.now().month if period == "month" else None
        )


class DaikinValueSensor(DaikinEntity, SensorEntity):
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
        super().__init__(
            device, coordinator, details.embedded_id, details.management_point_type
        )
        self._management_point_type = details.management_point_type
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
            characteristic = point.sensory_characteristic(self._value)
        else:
            characteristic = point.scalar_characteristic(self._value)
        result = characteristic.value if characteristic is not None else None
        _LOGGER.debug(
            "Device '%s' sensor '%s' value '%s'", self._device.name, self._value, result
        )
        return result


class DaikinLimitSensor(DaikinEntity, SensorEntity):
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
        super().__init__(
            device, coordinator, device.gateway_embedded_id or "gateway", "Gateway"
        )
        self._hass = hass
        self._config_entry = config_entry
        self._limit_key = limit_key
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self._device.id}_limitsensor_{self._limit_key}"
        self.entity_description = SENSOR_DESCRIPTIONS["RatelimitRemainingDay"]
        self.update_state()
        _LOGGER.info(
            "Device '%s' supports sensor '%s'",
            device.name,
            self._limit_key,
        )

    def update_state(self) -> None:
        """Refresh the rate-limit value."""
        self._attr_native_value = self.sensor_value()

    @property
    @override
    def available(self) -> bool:
        """Return coordinator availability without gateway cloud availability."""
        return self.coordinator.last_update_success

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    def sensor_value(self):
        """Return the current API rate-limit value."""
        daikin_api = self._config_entry.runtime_data.api
        return daikin_api.rate_limits[self._limit_key]
