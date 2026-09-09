"""Creates Sensor entities for the my-PV Home Assistant integration."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MyPVConfigEntry
from .entity import MyPVDataEntity

SENSOR_DESCRIPTIONS: Final[dict[str, dict[str, Any]]] = {
    "cur_eth_mode": {
        "enabled": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "cur_eth_mode",
    },
    "curr_l1": {
        "device_class": SensorDeviceClass.CURRENT,
        "translation_key": "curr_l1",
    },
    "curr_l2": {
        "device_class": SensorDeviceClass.CURRENT,
        "translation_key": "curr_l2",
    },
    "curr_l3": {
        "device_class": SensorDeviceClass.CURRENT,
        "translation_key": "curr_l3",
    },
    "curr_mains": {
        "device_class": SensorDeviceClass.CURRENT,
        "translation_key": "curr_l1",
    },
    "freq": {
        "device_class": SensorDeviceClass.FREQUENCY,
        "enabled": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "freq",
    },
    "power": {"device_class": SensorDeviceClass.POWER},
    "power_ac9": {"device_class": SensorDeviceClass.POWER},
    "power_act": {"device_class": SensorDeviceClass.POWER},
    "power_elwa2": {"device_class": SensorDeviceClass.POWER},
    "power_grid": {"device_class": SensorDeviceClass.POWER},
    "power_solar": {
        "device_class": SensorDeviceClass.POWER,
        "translation_key": "power_solar",
    },
    "screen_mode_flag": {"translation_key": "screen_mode_flag"},
    "temp1": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "translation_key": "temp1",
    },
    "temp2": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "translation_key": "temp2",
    },
    "temp3": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "translation_key": "temp3",
    },
    "temp4": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "translation_key": "temp4",
    },
    "temp_ps": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "enabled": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "temp_ps",
    },
    "uptime": {
        "device_class": SensorDeviceClass.DURATION,
        "enabled": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "translation_key": "uptime",
    },
    "volt_l1": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "volt_l1",
    },
    "volt_l2": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "volt_l2",
    },
    "volt_l3": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "volt_l3",
    },
    "volt_mains": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "volt_l1",
    },
    "volt_mains_l1": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "volt_l1",
    },
    "volt_mains_l2": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "volt_l2",
    },
    "volt_mains_l3": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "volt_l3",
    },
    "volt_solar": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "translation_key": "volt_solar",
    },
    "wifi_signal": {
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "enabled": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "wifi_signal",
    },
    "wifi_signal_strength": {
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "enabled": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "translation_key": "wifi_signal_strength",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV sensor."""
    coordinator = config_entry.runtime_data
    entities = []

    for key, config in coordinator.device.get_data_configurations().items():
        if config.get("type") != "boolean" and key in SENSOR_DESCRIPTIONS:
            sensor_description: dict = SENSOR_DESCRIPTIONS[key]

            device_class = None
            options = None
            state_class = None
            if config.get("type") == "enumeration":
                device_class = SensorDeviceClass.ENUM
                options = list(config["options"].keys())
            elif config.get("type") == "string":
                device_class = sensor_description.get("device_class")
            else:
                device_class = sensor_description.get("device_class")
                state_class = sensor_description.get(
                    "state_class", SensorStateClass.MEASUREMENT
                )

            translation_key: str | None = sensor_description.get("translation_key")
            if (
                (
                    key
                    in (
                        "curr_mains",
                        "curr_l1",
                    )
                    and not coordinator.device.supports_data("curr_l2")
                )
                or (
                    key in ("volt_mains", "volt_mains_l1", "volt_l1")
                    and not coordinator.device.supports_data("volt_l2")
                    and not coordinator.device.supports_data("volt_mains_l2")
                )
                or (key == "temp1" and not coordinator.device.supports_data("temp2"))
            ):
                translation_key = None

            suggested_display_precision = None
            divider = config.get("divider")
            if divider == 10:
                suggested_display_precision = 1
            elif divider:
                suggested_display_precision = 2

            entity_description = SensorEntityDescription(
                key=key,
                device_class=device_class,
                entity_category=sensor_description.get("entity_category"),
                translation_key=translation_key,
                native_unit_of_measurement=config.get("unit"),
                options=options,
                state_class=state_class,
                suggested_display_precision=suggested_display_precision,
                entity_registry_enabled_default=sensor_description.get("enabled", True),
            )
            entities.append(
                MyPVSensor(
                    coordinator,
                    entity_description,
                    coordinator.device.serial_number,
                )
            )

    async_add_entities(entities)


class MyPVSensor(MyPVDataEntity, SensorEntity):
    """Base my-PV Sensor."""

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self.coordinator.device.get_data_value(self.entity_description.key)
