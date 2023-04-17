"""Representation of Z-Wave sensors."""
from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import voluptuous as vol
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass, ConfigurationValueType, NodeStatus
from zwave_js_server.const.command_class.meter import (
    RESET_METER_OPTION_TARGET_VALUE,
    RESET_METER_OPTION_TYPE,
)
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import ConfigurationValue
from zwave_js_server.util.command_class.meter import get_meter_type

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_METER_TYPE,
    ATTR_METER_TYPE_NAME,
    ATTR_VALUE,
    DATA_CLIENT,
    DOMAIN,
    ENTITY_DESC_KEY_BATTERY,
    ENTITY_DESC_KEY_CO,
    ENTITY_DESC_KEY_CO2,
    ENTITY_DESC_KEY_CURRENT,
    ENTITY_DESC_KEY_ENERGY_MEASUREMENT,
    ENTITY_DESC_KEY_ENERGY_TOTAL_INCREASING,
    ENTITY_DESC_KEY_HUMIDITY,
    ENTITY_DESC_KEY_ILLUMINANCE,
    ENTITY_DESC_KEY_MEASUREMENT,
    ENTITY_DESC_KEY_POWER,
    ENTITY_DESC_KEY_POWER_FACTOR,
    ENTITY_DESC_KEY_PRESSURE,
    ENTITY_DESC_KEY_SIGNAL_STRENGTH,
    ENTITY_DESC_KEY_TARGET_TEMPERATURE,
    ENTITY_DESC_KEY_TEMPERATURE,
    ENTITY_DESC_KEY_TOTAL_INCREASING,
    ENTITY_DESC_KEY_VOLTAGE,
    LOGGER,
    SERVICE_RESET_METER,
)
from .discovery import ZwaveDiscoveryInfo
from .discovery_data_template import (
    NumericSensorDataTemplate,
    NumericSensorDataTemplateData,
)
from .entity import ZWaveBaseEntity
from .helpers import get_device_info, get_valueless_base_unique_id

PARALLEL_UPDATES = 0

STATUS_ICON: dict[NodeStatus, str] = {
    NodeStatus.ALIVE: "mdi:heart-pulse",
    NodeStatus.ASLEEP: "mdi:sleep",
    NodeStatus.AWAKE: "mdi:eye",
    NodeStatus.DEAD: "mdi:robot-dead",
    NodeStatus.UNKNOWN: "mdi:help-rhombus",
}


# These descriptions should include device class.
ENTITY_DESCRIPTION_KEY_DEVICE_CLASS_MAP: dict[
    tuple[str, str], SensorEntityDescription
] = {
    (ENTITY_DESC_KEY_BATTERY, PERCENTAGE): SensorEntityDescription(
        ENTITY_DESC_KEY_BATTERY,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    (ENTITY_DESC_KEY_CURRENT, UnitOfElectricCurrent.AMPERE): SensorEntityDescription(
        ENTITY_DESC_KEY_CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    (ENTITY_DESC_KEY_VOLTAGE, UnitOfElectricPotential.VOLT): SensorEntityDescription(
        ENTITY_DESC_KEY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    (
        ENTITY_DESC_KEY_VOLTAGE,
        UnitOfElectricPotential.MILLIVOLT,
    ): SensorEntityDescription(
        ENTITY_DESC_KEY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    (
        ENTITY_DESC_KEY_ENERGY_TOTAL_INCREASING,
        UnitOfEnergy.KILO_WATT_HOUR,
    ): SensorEntityDescription(
        ENTITY_DESC_KEY_ENERGY_TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    (ENTITY_DESC_KEY_POWER, UnitOfPower.WATT): SensorEntityDescription(
        ENTITY_DESC_KEY_POWER,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    (ENTITY_DESC_KEY_POWER_FACTOR, PERCENTAGE): SensorEntityDescription(
        ENTITY_DESC_KEY_POWER_FACTOR,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    (ENTITY_DESC_KEY_CO, CONCENTRATION_PARTS_PER_MILLION): SensorEntityDescription(
        ENTITY_DESC_KEY_CO,
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    (ENTITY_DESC_KEY_CO2, CONCENTRATION_PARTS_PER_MILLION): SensorEntityDescription(
        ENTITY_DESC_KEY_CO2,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    (ENTITY_DESC_KEY_HUMIDITY, PERCENTAGE): SensorEntityDescription(
        ENTITY_DESC_KEY_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    (ENTITY_DESC_KEY_ILLUMINANCE, LIGHT_LUX): SensorEntityDescription(
        ENTITY_DESC_KEY_ILLUMINANCE,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    (ENTITY_DESC_KEY_PRESSURE, UnitOfPressure.KPA): SensorEntityDescription(
        ENTITY_DESC_KEY_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
    ),
    (ENTITY_DESC_KEY_PRESSURE, UnitOfPressure.PSI): SensorEntityDescription(
        ENTITY_DESC_KEY_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PSI,
    ),
    (ENTITY_DESC_KEY_PRESSURE, UnitOfPressure.INHG): SensorEntityDescription(
        ENTITY_DESC_KEY_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.INHG,
    ),
    (ENTITY_DESC_KEY_PRESSURE, UnitOfPressure.MMHG): SensorEntityDescription(
        ENTITY_DESC_KEY_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.MMHG,
    ),
    (
        ENTITY_DESC_KEY_SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        ENTITY_DESC_KEY_SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
    (ENTITY_DESC_KEY_TEMPERATURE, UnitOfTemperature.CELSIUS): SensorEntityDescription(
        ENTITY_DESC_KEY_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    (
        ENTITY_DESC_KEY_TEMPERATURE,
        UnitOfTemperature.FAHRENHEIT,
    ): SensorEntityDescription(
        ENTITY_DESC_KEY_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    ),
    (
        ENTITY_DESC_KEY_TARGET_TEMPERATURE,
        UnitOfTemperature.CELSIUS,
    ): SensorEntityDescription(
        ENTITY_DESC_KEY_TARGET_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    (
        ENTITY_DESC_KEY_TARGET_TEMPERATURE,
        UnitOfTemperature.FAHRENHEIT,
    ): SensorEntityDescription(
        ENTITY_DESC_KEY_TARGET_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    ),
}

# These descriptions are without device class.
ENTITY_DESCRIPTION_KEY_MAP = {
    ENTITY_DESC_KEY_CO: SensorEntityDescription(
        ENTITY_DESC_KEY_CO,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ENTITY_DESC_KEY_ENERGY_MEASUREMENT: SensorEntityDescription(
        ENTITY_DESC_KEY_ENERGY_MEASUREMENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ENTITY_DESC_KEY_HUMIDITY: SensorEntityDescription(
        ENTITY_DESC_KEY_HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ENTITY_DESC_KEY_ILLUMINANCE: SensorEntityDescription(
        ENTITY_DESC_KEY_ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ENTITY_DESC_KEY_POWER_FACTOR: SensorEntityDescription(
        ENTITY_DESC_KEY_POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ENTITY_DESC_KEY_SIGNAL_STRENGTH: SensorEntityDescription(
        ENTITY_DESC_KEY_SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ENTITY_DESC_KEY_MEASUREMENT: SensorEntityDescription(
        ENTITY_DESC_KEY_MEASUREMENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ENTITY_DESC_KEY_TOTAL_INCREASING: SensorEntityDescription(
        ENTITY_DESC_KEY_TOTAL_INCREASING,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
}


def get_entity_description(
    data: NumericSensorDataTemplateData,
) -> SensorEntityDescription:
    """Return the entity description for the given data."""
    data_description_key = data.entity_description_key or ""
    data_unit = data.unit_of_measurement or ""
    return ENTITY_DESCRIPTION_KEY_DEVICE_CLASS_MAP.get(
        (data_description_key, data_unit),
        ENTITY_DESCRIPTION_KEY_MAP.get(
            data_description_key,
            SensorEntityDescription(
                "base_sensor", native_unit_of_measurement=data.unit_of_measurement
            ),
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_sensor(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Sensor."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []

        if info.platform_data:
            data: NumericSensorDataTemplateData = info.platform_data
        else:
            data = NumericSensorDataTemplateData()

        entity_description = get_entity_description(data)

        if info.platform_hint == "string_sensor":
            entities.append(
                ZWaveStringSensor(config_entry, driver, info, entity_description)
            )
        elif info.platform_hint == "numeric_sensor":
            entities.append(
                ZWaveNumericSensor(
                    config_entry,
                    driver,
                    info,
                    entity_description,
                    data.unit_of_measurement,
                )
            )
        elif info.platform_hint == "list_sensor":
            entities.append(
                ZWaveListSensor(config_entry, driver, info, entity_description)
            )
        elif info.platform_hint == "config_parameter":
            entities.append(
                ZWaveConfigParameterSensor(
                    config_entry, driver, info, entity_description
                )
            )
        elif info.platform_hint == "meter":
            entities.append(
                ZWaveMeterSensor(config_entry, driver, info, entity_description)
            )
        else:
            LOGGER.warning(
                "Sensor not implemented for %s/%s",
                info.platform_hint,
                info.primary_value.property_name,
            )
            return

        async_add_entities(entities)

    @callback
    def async_add_node_status_sensor(node: ZwaveNode) -> None:
        """Add node status sensor."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        async_add_entities([ZWaveNodeStatusSensor(config_entry, driver, node)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{SENSOR_DOMAIN}",
            async_add_sensor,
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_node_status_sensor",
            async_add_node_status_sensor,
        )
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RESET_METER,
        {
            vol.Optional(ATTR_METER_TYPE): vol.Coerce(int),
            vol.Optional(ATTR_VALUE): vol.Coerce(int),
        },
        "async_reset_meter",
    )


class ZwaveSensorBase(ZWaveBaseEntity, SensorEntity):
    """Basic Representation of a Z-Wave sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
        entity_description: SensorEntityDescription,
        unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize a ZWaveSensorBase entity."""
        super().__init__(config_entry, driver, info)
        self.entity_description = entity_description
        self._attr_native_unit_of_measurement = unit_of_measurement

        # Entity class attributes
        self._attr_force_update = True
        self._attr_name = self.generate_name(include_value_name=True)


class ZWaveStringSensor(ZwaveSensorBase):
    """Representation of a Z-Wave String sensor."""

    @property
    def native_value(self) -> str | None:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        return str(self.info.primary_value.value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement the value is expressed in."""
        if self.info.primary_value.metadata.unit is None:
            return None
        return str(self.info.primary_value.metadata.unit)


class ZWaveNumericSensor(ZwaveSensorBase):
    """Representation of a Z-Wave Numeric sensor."""

    @callback
    def on_value_update(self) -> None:
        """Handle scale changes for this value on value updated event."""
        data = NumericSensorDataTemplate().resolve_data(self.info.primary_value)
        self.entity_description = get_entity_description(data)
        self._attr_native_unit_of_measurement = data.unit_of_measurement

    @property
    def native_value(self) -> float:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return 0
        return round(float(self.info.primary_value.value), 2)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement the value is expressed in."""
        if self.entity_description.native_unit_of_measurement is not None:
            return self.entity_description.native_unit_of_measurement
        if self._attr_native_unit_of_measurement is not None:
            return self._attr_native_unit_of_measurement
        if self.info.primary_value.metadata.unit is None:
            return None

        return str(self.info.primary_value.metadata.unit)


class ZWaveMeterSensor(ZWaveNumericSensor):
    """Representation of a Z-Wave Meter CC sensor."""

    @property
    def extra_state_attributes(self) -> Mapping[str, int | str] | None:
        """Return extra state attributes."""
        if meter_type := get_meter_type(self.info.primary_value):
            return {
                ATTR_METER_TYPE: meter_type.value,
                ATTR_METER_TYPE_NAME: meter_type.name,
            }
        return None

    async def async_reset_meter(
        self, meter_type: int | None = None, value: int | None = None
    ) -> None:
        """Reset meter(s) on device."""
        node = self.info.node
        primary_value = self.info.primary_value
        if (endpoint := primary_value.endpoint) is None:
            raise HomeAssistantError("Missing endpoint on device.")
        options = {}
        if meter_type is not None:
            options[RESET_METER_OPTION_TYPE] = meter_type
        if value is not None:
            options[RESET_METER_OPTION_TARGET_VALUE] = value
        args = [options] if options else []
        await node.endpoints[endpoint].async_invoke_cc_api(
            CommandClass.METER, "reset", *args, wait_for_result=False
        )
        LOGGER.debug(
            "Meters on node %s endpoint %s reset with the following options: %s",
            node,
            primary_value.endpoint,
            options,
        )


class ZWaveListSensor(ZwaveSensorBase):
    """Representation of a Z-Wave Numeric sensor with multiple states."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
        entity_description: SensorEntityDescription,
        unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize a ZWaveListSensor entity."""
        super().__init__(
            config_entry, driver, info, entity_description, unit_of_measurement
        )

        # Entity class attributes
        self._attr_name = self.generate_name(include_value_name=True)

    @property
    def native_value(self) -> str | None:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        if (
            str(self.info.primary_value.value)
            not in self.info.primary_value.metadata.states
        ):
            return str(self.info.primary_value.value)
        return str(
            self.info.primary_value.metadata.states[str(self.info.primary_value.value)]
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the device specific state attributes."""
        if (value := self.info.primary_value.value) is None:
            return None
        # add the value's int value as property for multi-value (list) items
        return {ATTR_VALUE: value}


class ZWaveConfigParameterSensor(ZwaveSensorBase):
    """Representation of a Z-Wave config parameter sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
        entity_description: SensorEntityDescription,
        unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize a ZWaveConfigParameterSensor entity."""
        super().__init__(
            config_entry, driver, info, entity_description, unit_of_measurement
        )
        self._primary_value = cast(ConfigurationValue, self.info.primary_value)

        property_key_name = self.info.primary_value.property_key_name
        # Entity class attributes
        self._attr_name = self.generate_name(
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[property_key_name] if property_key_name else None,
            name_prefix="Config parameter",
        )

    @property
    def native_value(self) -> str | None:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        if (
            self._primary_value.configuration_value_type == ConfigurationValueType.RANGE
            or (
                str(self.info.primary_value.value)
                not in self.info.primary_value.metadata.states
            )
        ):
            return str(self.info.primary_value.value)
        return str(
            self.info.primary_value.metadata.states[str(self.info.primary_value.value)]
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the device specific state attributes."""
        if (
            self._primary_value.configuration_value_type == ConfigurationValueType.RANGE
            or (value := self.info.primary_value.value) is None
        ):
            return None
        # add the value's int value as property for multi-value (list) items
        return {ATTR_VALUE: value}


class ZWaveNodeStatusSensor(SensorEntity):
    """Representation of a node status sensor."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, node: ZwaveNode
    ) -> None:
        """Initialize a generic Z-Wave device entity."""
        self.config_entry = config_entry
        self.node = node

        # Entity class attributes
        self._attr_name = "Node status"
        self._base_unique_id = get_valueless_base_unique_id(driver, node)
        self._attr_unique_id = f"{self._base_unique_id}.node_status"
        # device may not be precreated in main handler yet
        self._attr_device_info = get_device_info(driver, node)

    async def async_poll_value(self, _: bool) -> None:
        """Poll a value."""
        LOGGER.error(
            "There is no value to refresh for this entity so the zwave_js.refresh_value"
            " service won't work for it"
        )

    @callback
    def _status_changed(self, _: dict) -> None:
        """Call when status event is received."""
        self._attr_native_value = self.node.status.name.lower()
        self.async_write_ha_state()

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        return STATUS_ICON[self.node.status]

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        # Add value_changed callbacks.
        for evt in ("wake up", "sleep", "dead", "alive"):
            self.async_on_remove(self.node.on(evt, self._status_changed))
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.unique_id}_poll_value",
                self.async_poll_value,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._base_unique_id}_remove_entity",
                self.async_remove,
            )
        )
        self._attr_native_value: str = self.node.status.name.lower()
        self.async_write_ha_state()
