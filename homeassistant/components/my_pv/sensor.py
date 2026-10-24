"""Creates Sensor entities for the my-PV integration."""

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

from .coordinator import MyPVConfigEntry, MyPVCoordinator
from .entity import MyPVDataEntity

PARALLEL_UPDATES = 0

ENTITY_DESCRIPTIONS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key="cur_eth_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="cur_eth_mode",
    ),
    SensorEntityDescription(
        key="curr_l1",
        device_class=SensorDeviceClass.CURRENT,
        translation_key="curr_l1",
    ),
    SensorEntityDescription(
        key="curr_l2",
        device_class=SensorDeviceClass.CURRENT,
        translation_key="curr_l2",
    ),
    SensorEntityDescription(
        key="curr_l3",
        device_class=SensorDeviceClass.CURRENT,
        translation_key="curr_l3",
    ),
    SensorEntityDescription(
        key="curr_mains",
        device_class=SensorDeviceClass.CURRENT,
        suggested_display_precision=1,
        translation_key="curr_l1",
    ),
    SensorEntityDescription(
        key="freq",
        device_class=SensorDeviceClass.FREQUENCY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        translation_key="freq",
    ),
    SensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="power_ac9",
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="power_act",
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="power_elwa2",
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="power_grid",
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="power_solar",
        device_class=SensorDeviceClass.POWER,
        translation_key="power_solar",
    ),
    SensorEntityDescription(
        key="screen_mode_flag",
        translation_key="screen_mode_flag",
    ),
    SensorEntityDescription(
        key="temp1",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        translation_key="temp1",
    ),
    SensorEntityDescription(
        key="temp2",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        translation_key="temp2",
    ),
    SensorEntityDescription(
        key="temp3",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        translation_key="temp3",
    ),
    SensorEntityDescription(
        key="temp4",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        translation_key="temp4",
    ),
    SensorEntityDescription(
        key="temp_ps",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        translation_key="temp_ps",
    ),
    SensorEntityDescription(
        key="uptime",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="uptime",
    ),
    SensorEntityDescription(
        key="volt_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="volt_l1",
    ),
    SensorEntityDescription(
        key="volt_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="volt_l2",
    ),
    SensorEntityDescription(
        key="volt_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="volt_l3",
    ),
    SensorEntityDescription(
        key="volt_mains",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="volt_l1",
    ),
    SensorEntityDescription(
        key="volt_mains_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        translation_key="volt_l1",
    ),
    SensorEntityDescription(
        key="volt_mains_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        translation_key="volt_l2",
    ),
    SensorEntityDescription(
        key="volt_mains_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        translation_key="volt_l3",
    ),
    SensorEntityDescription(
        key="volt_solar",
        device_class=SensorDeviceClass.VOLTAGE,
        translation_key="volt_solar",
    ),
    SensorEntityDescription(
        key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="wifi_signal",
    ),
    SensorEntityDescription(
        key="wifi_signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="wifi_signal_strength",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV sensor."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MyPVSensor(coordinator, entity_description, config)
        for entity_description in ENTITY_DESCRIPTIONS
        if (config := coordinator.device.get_data_configuration(entity_description.key))
        and config.get("type") != "boolean"
    )


class MyPVSensor(MyPVDataEntity, SensorEntity):
    """Base my-PV Sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: SensorEntityDescription,
        config: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)

        self._attr_native_unit_of_measurement = config.get("unit")

        match config.get("type"):
            case "enumeration":
                self._attr_device_class = SensorDeviceClass.ENUM
                self._attr_options = list(config["options"].keys())
                self._attr_state_class = None
            case "string":
                self._attr_state_class = None
            case _:
                self._attr_state_class = (
                    entity_description.state_class or SensorStateClass.MEASUREMENT
                )

        # On single phase devices, or devices with a single temperature sensor,
        # use the device class name instead of a numbered name.
        device = coordinator.device
        key = entity_description.key
        if (
            (key in ("curr_mains", "curr_l1") and not device.supports_data("curr_l2"))
            or (
                key in ("volt_mains", "volt_mains_l1", "volt_l1")
                and not device.supports_data("volt_l2")
                and not device.supports_data("volt_mains_l2")
            )
            or (key == "temp1" and not device.supports_data("temp2"))
        ):
            self._attr_translation_key = None

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self.coordinator.device.get_data_value(self.entity_description.key)
