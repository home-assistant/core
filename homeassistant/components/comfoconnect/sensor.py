"""Platform to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
from __future__ import annotations

from dataclasses import dataclass

from pycomfoconnect import (
    SENSOR_BYPASS_STATE,
    SENSOR_CURRENT_RMOT,
    SENSOR_DAYS_TO_REPLACE_FILTER,
    SENSOR_FAN_EXHAUST_DUTY,
    SENSOR_FAN_EXHAUST_FLOW,
    SENSOR_FAN_EXHAUST_SPEED,
    SENSOR_FAN_SUPPLY_DUTY,
    SENSOR_FAN_SUPPLY_FLOW,
    SENSOR_FAN_SUPPLY_SPEED,
    SENSOR_HUMIDITY_EXHAUST,
    SENSOR_HUMIDITY_EXTRACT,
    SENSOR_HUMIDITY_OUTDOOR,
    SENSOR_HUMIDITY_SUPPLY,
    SENSOR_POWER_CURRENT,
    SENSOR_POWER_TOTAL,
    SENSOR_PREHEATER_POWER_CURRENT,
    SENSOR_PREHEATER_POWER_TOTAL,
    SENSOR_TEMPERATURE_EXHAUST,
    SENSOR_TEMPERATURE_EXTRACT,
    SENSOR_TEMPERATURE_OUTDOOR,
    SENSOR_TEMPERATURE_SUPPLY,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_RESOURCES,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge
from .const import _LOGGER

ATTR_AIR_FLOW_EXHAUST = "air_flow_exhaust"
ATTR_AIR_FLOW_SUPPLY = "air_flow_supply"
ATTR_BYPASS_STATE = "bypass_state"
ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_CURRENT_RMOT = "current_rmot"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_DAYS_TO_REPLACE_FILTER = "days_to_replace_filter"
ATTR_EXHAUST_FAN_DUTY = "exhaust_fan_duty"
ATTR_EXHAUST_FAN_SPEED = "exhaust_fan_speed"
ATTR_EXHAUST_HUMIDITY = "exhaust_humidity"
ATTR_EXHAUST_TEMPERATURE = "exhaust_temperature"
ATTR_OUTSIDE_HUMIDITY = "outside_humidity"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"
ATTR_POWER_CURRENT = "power_usage"
ATTR_POWER_TOTAL = "power_total"
ATTR_PREHEATER_POWER_CURRENT = "preheater_power_usage"
ATTR_PREHEATER_POWER_TOTAL = "preheater_power_total"
ATTR_SUPPLY_FAN_DUTY = "supply_fan_duty"
ATTR_SUPPLY_FAN_SPEED = "supply_fan_speed"
ATTR_SUPPLY_HUMIDITY = "supply_humidity"
ATTR_SUPPLY_TEMPERATURE = "supply_temperature"


@dataclass
class ComfoconnectRequiredKeysMixin:
    """Mixin for required keys."""

    sensor_id: int


@dataclass
class ComfoconnectSensorEntityDescription(
    SensorEntityDescription, ComfoconnectRequiredKeysMixin
):
    """Describes Comfoconnect sensor entity."""

    multiplier: float = 1


SENSOR_TYPES = (
    ComfoconnectSensorEntityDescription(
        key=ATTR_CURRENT_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Inside temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        sensor_id=SENSOR_TEMPERATURE_EXTRACT,
        multiplier=0.1,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_CURRENT_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Inside humidity",
        native_unit_of_measurement=PERCENTAGE,
        sensor_id=SENSOR_HUMIDITY_EXTRACT,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_CURRENT_RMOT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Current RMOT",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        sensor_id=SENSOR_CURRENT_RMOT,
        multiplier=0.1,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_OUTSIDE_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Outside temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        sensor_id=SENSOR_TEMPERATURE_OUTDOOR,
        multiplier=0.1,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_OUTSIDE_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Outside humidity",
        native_unit_of_measurement=PERCENTAGE,
        sensor_id=SENSOR_HUMIDITY_OUTDOOR,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        sensor_id=SENSOR_TEMPERATURE_SUPPLY,
        multiplier=0.1,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply humidity",
        native_unit_of_measurement=PERCENTAGE,
        sensor_id=SENSOR_HUMIDITY_SUPPLY,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_FAN_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply fan speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fan-plus",
        sensor_id=SENSOR_FAN_SUPPLY_SPEED,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_FAN_DUTY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply fan duty",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fan-plus",
        sensor_id=SENSOR_FAN_SUPPLY_DUTY,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_FAN_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust fan speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fan-minus",
        sensor_id=SENSOR_FAN_EXHAUST_SPEED,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_FAN_DUTY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust fan duty",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fan-minus",
        sensor_id=SENSOR_FAN_EXHAUST_DUTY,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        sensor_id=SENSOR_TEMPERATURE_EXHAUST,
        multiplier=0.1,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust humidity",
        native_unit_of_measurement=PERCENTAGE,
        sensor_id=SENSOR_HUMIDITY_EXHAUST,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_AIR_FLOW_SUPPLY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply airflow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:fan-plus",
        sensor_id=SENSOR_FAN_SUPPLY_FLOW,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_AIR_FLOW_EXHAUST,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust airflow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:fan-minus",
        sensor_id=SENSOR_FAN_EXHAUST_FLOW,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_BYPASS_STATE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Bypass state",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:camera-iris",
        sensor_id=SENSOR_BYPASS_STATE,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_DAYS_TO_REPLACE_FILTER,
        name="Days to replace filter",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:calendar",
        sensor_id=SENSOR_DAYS_TO_REPLACE_FILTER,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_POWER_CURRENT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        name="Power usage",
        native_unit_of_measurement=UnitOfPower.WATT,
        sensor_id=SENSOR_POWER_CURRENT,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_POWER_TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Energy total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        sensor_id=SENSOR_POWER_TOTAL,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_PREHEATER_POWER_CURRENT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        name="Preheater power usage",
        native_unit_of_measurement=UnitOfPower.WATT,
        sensor_id=SENSOR_PREHEATER_POWER_CURRENT,
        entity_registry_enabled_default=False,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_PREHEATER_POWER_TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Preheater energy total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        sensor_id=SENSOR_PREHEATER_POWER_TOTAL,
        entity_registry_enabled_default=False,
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_RESOURCES, default=[]): vol.All(
            cv.ensure_list, [vol.In([desc.key for desc in SENSOR_TYPES])]
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ComfoConnect sensor platform."""
    # migrated_entry = hass.data[DOMAIN].get(SOURCE_IMPORT)

    # if migrated_entry is None:
    #     return

    _LOGGER.warning(
        "Configuring ComfoConnect sensors using YAML is being removed. All available sensors"
        "have been imported into the UI automatically (disabled by default). Remove "
        "the ComfoConnect sensor configuration from your configuration.yaml file and "
        "restart Home Assistant to fix this issue"
    )

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_sensor",
        breaks_in_ha_version="2023.5.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_sensor",
    )

    # # No more setup from configuration.yaml, just do a one-time import
    # # We only import configs from YAML if it hasn't been imported. If there is a config
    # # entry marked with SOURCE_IMPORT, it means the YAML config has been imported.
    # for entry in hass.config_entries.async_entries(DOMAIN):
    #     if entry.source == SOURCE_IMPORT:
    #         # Remove the artificial entry since it's no longer needed.
    #         hass.data[DOMAIN].pop(SOURCE_IMPORT)

    # Remove the artificial entry since it's no longer needed.
    hass.data[DOMAIN].pop(SOURCE_IMPORT)
    return


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ComfoConnect sensor platform."""
    # ccb = hass.data[DOMAIN]
    ccb = hass.data[DOMAIN][entry.entry_id]

    # # Import from config
    # conf = hass.data[DOMAIN].get(SOURCE_IMPORT)
    # if conf is not None:
    #     return

    # For user input from config flow
    async_add_entities(
        [ComfoConnectSensor(ccb, entry, description) for description in SENSOR_TYPES],
        True,
    )


class ComfoConnectSensor(SensorEntity):
    """Representation of a ComfoConnect sensor."""

    _attr_should_poll = False
    entity_description: ComfoconnectSensorEntityDescription

    def __init__(
        self,
        ccb: ComfoConnectBridge,
        entry: ConfigEntry,
        description: ComfoconnectSensorEntityDescription,
    ) -> None:
        """Initialize the ComfoConnect sensor."""
        self._ccb = ccb
        self.entity_description = description
        self._attr_name = f"{ccb.name} {description.name}"
        self._attr_unique_id = f"{ccb.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ccb.unique_id)},
        )

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""
        _LOGGER.debug(
            "Registering for sensor %s (%d)",
            self.entity_description.key,
            self.entity_description.sensor_id,
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(
                    self.entity_description.sensor_id
                ),
                self._handle_update,
            )
        )
        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, self.entity_description.sensor_id
        )

    def _handle_update(self, value):
        """Handle update callbacks."""
        _LOGGER.debug(
            "Handle update for sensor %s (%d): %s",
            self.entity_description.key,
            self.entity_description.sensor_id,
            value,
        )
        self._attr_native_value = round(value * self.entity_description.multiplier, 2)
        self.schedule_update_ha_state()
