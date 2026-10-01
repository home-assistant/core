"""Support for Daikin AC sensors."""

import logging
from typing import Any, cast, override

from homeassistant.components.sensor import CONF_STATE_CLASS, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ICON, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ENABLED_DEFAULT,
    ENTITY_CATEGORY,
    MODEL_ATTRIBUTE,
    SENSOR_PERIOD_MONTHLY,
    SENSOR_PERIOD_WEEKLY,
    SENSOR_PERIOD_YEARLY,
    SENSOR_PERIODS,
    TRANSLATION_KEY,
    VALUE_SENSOR_MAPPING,
)
from .coordinator import OnectaRuntimeData
from .device import DaikinOnectaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, async_add_entities):
    """Old way of setting up the Daikin sensors.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


def handle_energy_sensors(
    coordinator,
    device,
    management_point,
    sensor_type,
    source,
    sensors,
    datatype,
):
    """Add energy sensors for the periods exposed by an energy source."""
    for mode in ("heating", "cooling"):
        series = getattr(source, mode)
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
                        management_point.embedded_id,
                        management_point.management_point_type,
                        sensor_type,
                        mode,
                        SENSOR_PERIOD_MONTHLY,
                        datatype,
                    )
                )
            if period in SENSOR_PERIODS:
                sensors.append(
                    DaikinEnergySensor(
                        device,
                        coordinator,
                        management_point.embedded_id,
                        management_point.management_point_type,
                        sensor_type,
                        mode,
                        period,
                        datatype,
                    )
                )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin sensors based on config_entry."""
    onecta_data: OnectaRuntimeData = config_entry.runtime_data
    coordinator = onecta_data.coordinator
    sensors: list[SensorEntity] = []
    supported_management_point_types = {
        "domesticHotWaterTank",
        "domesticHotWaterFlowThrough",
        "climateControl",
        "climateControlMainZone",
    }
    for device in onecta_data.devices.values():
        sensors.append(
            DaikinLimitSensor(hass, config_entry, device, coordinator, "remaining_day")
        )
        for management_point in device.device.management_points:
            management_point_type = management_point.management_point_type
            embedded_id = management_point.embedded_id

            for (
                value,
                characteristic,
            ) in management_point.simple_characteristics().items():
                if value not in VALUE_SENSOR_MAPPING:
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
                    and management_point_type in supported_management_point_types
                ):
                    continue
                if characteristic.value is not None:
                    sensors.append(
                        DaikinValueSensor(
                            device,
                            coordinator,
                            embedded_id,
                            management_point_type,
                            None,
                            value,
                        )
                    )

            if management_point.sensory_data is not None:
                sensory_data = management_point.sensory_data.value
                sensors.extend(
                    DaikinValueSensor(
                        device,
                        coordinator,
                        embedded_id,
                        management_point_type,
                        "sensoryData",
                        sensor,
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
                    if sensor in VALUE_SENSOR_MAPPING
                    and getattr(
                        sensory_data,
                        cast(dict[str, Any], VALUE_SENSOR_MAPPING[sensor])[
                            MODEL_ATTRIBUTE
                        ],
                    )
                    is not None
                )

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
                            sensor_type,
                            source,
                            sensors,
                            datatype,
                        )

    async_add_entities(sensors)


class DaikinEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a power/energy sensor."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator,
        embedded_id,
        management_point_type,
        sensor_type,
        operation_mode,
        period,
        datatype,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(coordinator)
        self._device = device
        self._management_point_type = management_point_type
        mpt = management_point_type[0].upper() + management_point_type[1:]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.id + self._management_point_type)},
            name=self._device.name + " " + mpt,
            **(
                {"via_device_id": self._device.ha_device_id}
                if self._device.ha_device_id is not None
                else {}
            ),
        )
        self._device.fill_device_info(self._attr_device_info, management_point_type)
        self._embedded_id = embedded_id
        self._operation_mode = operation_mode
        self._attr_has_entity_name = True
        self._period = period
        self._datatype = datatype
        period_name = SENSOR_PERIODS[period]
        buildname = (
            f"{operation_mode.capitalize()}{period_name}"
            f"{sensor_type.capitalize()}{datatype.capitalize()}"
        )
        sensor_settings = cast(dict[str, Any], VALUE_SENSOR_MAPPING[buildname])
        self._attr_icon = sensor_settings[CONF_ICON]
        self._attr_device_class = sensor_settings[CONF_DEVICE_CLASS]
        self._attr_entity_registry_enabled_default = sensor_settings[ENABLED_DEFAULT]
        self._attr_state_class = sensor_settings[CONF_STATE_CLASS]
        self._attr_entity_category = sensor_settings[ENTITY_CATEGORY]
        self._attr_translation_key = sensor_settings[TRANSLATION_KEY]
        self._attr_native_unit_of_measurement = sensor_settings[
            CONF_UNIT_OF_MEASUREMENT
        ]
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{self._device.id}_{self._management_point_type}_{sensor_type}_{self._operation_mode}_{self._period}"
        self.update_state()
        _LOGGER.info(
            "Device '%s:%s' supports sensor '%s'",
            device.name,
            self._embedded_id,
            buildname,
        )

    def update_state(self) -> None:
        """Update the native sensor value."""
        self._attr_native_value = self.sensor_value()

    @property
    @override
    def available(self) -> bool:
        """Return whether the device is available."""
        return self._device.available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_state()
        self.async_write_ha_state()

    def sensor_value(self):
        """Return the aggregated energy value."""
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

        energy_values = [0 if value is None else value for value in period_data]
        if self._period == SENSOR_PERIOD_WEEKLY:
            start_index = 7
            end_index = len(energy_values)
        elif self._period == SENSOR_PERIOD_MONTHLY:
            start_index = 11 + dt_util.now().month
            end_index = start_index + 1
        else:
            start_index = 12
            end_index = len(energy_values)
        return round(sum(energy_values[start_index:end_index]), 3)


class DaikinValueSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Daikin value sensor."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator,
        embedded_id,
        management_point_type,
        sub_type,
        value,
    ) -> None:
        """Initialize the value sensor."""
        _LOGGER.info(
            "DaikinValueSensor '%s' '%s' '%s'", management_point_type, sub_type, value
        )
        super().__init__(coordinator)
        self._device = device
        self._management_point_type = management_point_type
        mpt = management_point_type[0].upper() + management_point_type[1:]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.id + self._management_point_type)},
            name=self._device.name + " " + mpt,
            **(
                {"via_device_id": self._device.ha_device_id}
                if self._device.ha_device_id is not None
                else {}
            ),
        )
        self._device.fill_device_info(self._attr_device_info, management_point_type)
        self._embedded_id = embedded_id
        self._sub_type = sub_type
        self._value = value
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_has_entity_name = True
        sensor_settings = cast(dict[str, Any], VALUE_SENSOR_MAPPING[value])
        self._attr_icon = sensor_settings[CONF_ICON]
        self._attr_device_class = sensor_settings[CONF_DEVICE_CLASS]
        self._attr_entity_registry_enabled_default = sensor_settings[ENABLED_DEFAULT]
        self._attr_state_class = sensor_settings[CONF_STATE_CLASS]
        self._attr_entity_category = sensor_settings[ENTITY_CATEGORY]
        self._attr_native_unit_of_measurement = sensor_settings[
            CONF_UNIT_OF_MEASUREMENT
        ]
        self._attr_translation_key = sensor_settings[TRANSLATION_KEY]
        self._attr_unique_id = f"{self._device.id}_{self._management_point_type}_{self._sub_type}_{self._value}"
        self.update_state()
        _LOGGER.info(
            "Device '%s:%s' supports sensor '%s'",
            device.name,
            self._embedded_id,
            self._value,
        )

    def update_state(self) -> None:
        """Update the native sensor value."""
        self._attr_native_value = self.sensor_value()

    @property
    @override
    def available(self) -> bool:
        """Return whether the device is available."""
        return self._device.available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
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
            sensor_settings = cast(dict[str, Any], VALUE_SENSOR_MAPPING[self._value])
            attribute = sensor_settings.get(MODEL_ATTRIBUTE)
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
    """Representation of a Daikin API limit sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: DaikinOnectaDevice,
        coordinator,
        limit_key,
    ) -> None:
        """Initialize the API limit sensor."""
        _LOGGER.info("Device '%s' LimitSensor '%s'", device.name, limit_key)
        super().__init__(coordinator)
        self._hass = hass
        self._config_entry = config_entry
        self._device = device
        self._limit_key = limit_key
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self._device.id}_limitsensor_{self._limit_key}"
        sensor_settings = cast(
            dict[str, Any], VALUE_SENSOR_MAPPING["RatelimitRemainingDay"]
        )
        self._attr_icon = sensor_settings[CONF_ICON]
        self._attr_device_class = sensor_settings[CONF_DEVICE_CLASS]
        self._attr_entity_registry_enabled_default = sensor_settings[ENABLED_DEFAULT]
        self._attr_state_class = sensor_settings[CONF_STATE_CLASS]
        self._attr_entity_category = sensor_settings[ENTITY_CATEGORY]
        self._attr_native_unit_of_measurement = sensor_settings[
            CONF_UNIT_OF_MEASUREMENT
        ]
        self._attr_translation_key = sensor_settings[TRANSLATION_KEY]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.id + "gateway")},
            name=self._device.name + " " + "Gateway",
            **(
                {"via_device_id": self._device.ha_device_id}
                if self._device.ha_device_id is not None
                else {}
            ),
        )
        self._device.fill_device_info(self._attr_device_info, "gateway")
        self.update_state()
        _LOGGER.info(
            "Device '%s' supports sensor '%s'",
            device.name,
            self._limit_key,
        )

    def update_state(self) -> None:
        """Update the native sensor value."""
        self._attr_native_value = self.sensor_value()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_state()
        self.async_write_ha_state()

    def sensor_value(self):
        """Return the current API limit value."""
        daikin_api = self._config_entry.runtime_data.daikin_api
        return daikin_api.rate_limits[self._limit_key]
