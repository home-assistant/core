"""Binary sensor platform for Compit integration."""

from dataclasses import dataclass

from compit_inext_api.consts import CompitParameter

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

PARALLEL_UPDATES = 0
NO_SENSOR = "no_sensor"
ON_STATES = ["on", "yes", "charging", "alert", "exceeded"]


@dataclass(frozen=True, kw_only=True)
class CompitDeviceDescription:
    """Class to describe a Compit device."""

    name: str
    """Name of the device."""

    parameters: dict[CompitParameter, BinarySensorEntityDescription]
    """Parameters of the device."""


DEVICE_DEFINITIONS: dict[int, CompitDeviceDescription] = {
    12: CompitDeviceDescription(
        name="Nano Color",
        parameters={
            CompitParameter.CO2_LEVEL: BinarySensorEntityDescription(
                key=CompitParameter.CO2_LEVEL.value,
                translation_key="co2_level",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        },
    ),
    78: CompitDeviceDescription(
        name="SPM - Nano Color 2",
        parameters={
            CompitParameter.DUST_ALERT: BinarySensorEntityDescription(
                key=CompitParameter.DUST_ALERT.value,
                translation_key="dust_alert",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            CompitParameter.TEMPERATURE_ALERT: BinarySensorEntityDescription(
                key=CompitParameter.TEMPERATURE_ALERT.value,
                translation_key="temperature_alert",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            CompitParameter.CO2_ALERT: BinarySensorEntityDescription(
                key=CompitParameter.CO2_ALERT.value,
                translation_key="co2_alert",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        },
    ),
    223: CompitDeviceDescription(
        name="Nano Color 2",
        parameters={
            CompitParameter.AIRING: BinarySensorEntityDescription(
                key=CompitParameter.AIRING.value,
                translation_key="airing",
                device_class=BinarySensorDeviceClass.WINDOW,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            CompitParameter.CO2_LEVEL: BinarySensorEntityDescription(
                key=CompitParameter.CO2_LEVEL.value,
                translation_key="co2_level",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        },
    ),
    225: CompitDeviceDescription(
        name="SPM - Nano Color",
        parameters={
            CompitParameter.CO2_LEVEL: BinarySensorEntityDescription(
                key=CompitParameter.CO2_LEVEL.value,
                translation_key="co2_level",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        },
    ),
    226: CompitDeviceDescription(
        name="AF-1",
        parameters={
            CompitParameter.BATTERY_CHARGE_STATUS: BinarySensorEntityDescription(
                key=CompitParameter.BATTERY_CHARGE_STATUS.value,
                device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            CompitParameter.HAS_BATTERY: BinarySensorEntityDescription(
                key=CompitParameter.HAS_BATTERY.value,
                translation_key="has_battery",
                device_class=BinarySensorDeviceClass.BATTERY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            CompitParameter.HAS_EXTERNAL_POWER: BinarySensorEntityDescription(
                key=CompitParameter.HAS_EXTERNAL_POWER.value,
                translation_key="has_external_power",
                device_class=BinarySensorDeviceClass.PLUG,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            CompitParameter.PUMP_STATUS: BinarySensorEntityDescription(
                key=CompitParameter.PUMP_STATUS.value,
                translation_key="pump_status",
                device_class=BinarySensorDeviceClass.RUNNING,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        },
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Compit binary sensor entities from a config entry."""

    coordinator = entry.runtime_data
    binary_sensor_entities = []
    for device_id, device in coordinator.connector.all_devices.items():
        device_definition = DEVICE_DEFINITIONS.get(device.definition.code)

        if not device_definition:
            continue

        for code, entity_description in device_definition.parameters.items():
            if coordinator.connector.get_current_value(device_id, code) == NO_SENSOR:
                continue

            binary_sensor_entities.append(
                CompitBinarySensor(
                    coordinator,
                    device_id,
                    device_definition.name,
                    code,
                    entity_description,
                )
            )

    async_add_devices(binary_sensor_entities)


class CompitBinarySensor(
    CoordinatorEntity[CompitDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Compit binary sensor entity."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device_id: int,
        device_name: str,
        parameter_code: CompitParameter,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = entity_description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device_name,
            manufacturer=MANUFACTURER_NAME,
            model=device_name,
        )
        self.parameter_code = parameter_code

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.connector.get_device(self.device_id) is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        value = self.coordinator.connector.get_current_value(
            self.device_id, self.parameter_code
        )

        if value is None:
            return None

        return value in ON_STATES
