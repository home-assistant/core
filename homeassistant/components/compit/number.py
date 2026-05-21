"""Number platform for Compit integration."""

from dataclasses import dataclass

from compit_inext_api.consts import CompitParameter

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CompitDeviceDescription:
    """Class to describe a Compit device."""

    name: str
    """Name of the device."""

    parameters: list[NumberEntityDescription]
    """Parameters of the device."""


DESCRIPTIONS: dict[CompitParameter, NumberEntityDescription] = {
    CompitParameter.TARGET_TEMPERATURE_COMFORT: NumberEntityDescription(
        key=CompitParameter.TARGET_TEMPERATURE_COMFORT.value,
        translation_key="target_temperature_comfort",
        native_min_value=0,
        native_max_value=40,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.TARGET_TEMPERATURE_ECO_WINTER: NumberEntityDescription(
        key=CompitParameter.TARGET_TEMPERATURE_ECO_WINTER.value,
        translation_key="target_temperature_eco_winter",
        native_min_value=0,
        native_max_value=40,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.TARGET_TEMPERATURE_ECO_COOLING: NumberEntityDescription(
        key=CompitParameter.TARGET_TEMPERATURE_ECO_COOLING.value,
        translation_key="target_temperature_eco_cooling",
        native_min_value=0,
        native_max_value=40,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.TARGET_TEMPERATURE_OUT_OF_HOME: NumberEntityDescription(
        key=CompitParameter.TARGET_TEMPERATURE_OUT_OF_HOME.value,
        translation_key="target_temperature_out_of_home",
        native_min_value=0,
        native_max_value=40,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.TARGET_TEMPERATURE_ECO: NumberEntityDescription(
        key=CompitParameter.TARGET_TEMPERATURE_ECO.value,
        translation_key="target_temperature_eco",
        native_min_value=0,
        native_max_value=40,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.TARGET_TEMPERATURE_HOLIDAY: NumberEntityDescription(
        key=CompitParameter.TARGET_TEMPERATURE_HOLIDAY.value,
        translation_key="target_temperature_holiday",
        native_min_value=0,
        native_max_value=40,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.TARGET_TEMPERATURE_CONST: NumberEntityDescription(
        key=CompitParameter.TARGET_TEMPERATURE_CONST.value,
        translation_key="target_temperature_const",
        native_min_value=0,
        native_max_value=95,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.HEATING_TARGET_TEMPERATURE_CONST: NumberEntityDescription(
        key=CompitParameter.HEATING_TARGET_TEMPERATURE_CONST.value,
        translation_key="heating_target_temperature_const",
        native_min_value=0,
        native_max_value=95,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.MIXER_TARGET_TEMPERATURE: NumberEntityDescription(
        key=CompitParameter.MIXER_TARGET_TEMPERATURE.value,
        translation_key="mixer_target_temperature",
        native_min_value=0,
        native_max_value=90,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.MIXER1_TARGET_TEMPERATURE: NumberEntityDescription(
        key=CompitParameter.MIXER1_TARGET_TEMPERATURE.value,
        translation_key="mixer_target_temperature_zone",
        native_min_value=0,
        native_max_value=95,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        translation_placeholders={"zone": "1"},
    ),
    CompitParameter.MIXER2_TARGET_TEMPERATURE: NumberEntityDescription(
        key=CompitParameter.MIXER2_TARGET_TEMPERATURE.value,
        translation_key="mixer_target_temperature_zone",
        native_min_value=0,
        native_max_value=95,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        translation_placeholders={"zone": "2"},
    ),
    CompitParameter.BOILER_TARGET_TEMPERATURE: NumberEntityDescription(
        key=CompitParameter.BOILER_TARGET_TEMPERATURE.value,
        translation_key="boiler_target_temperature",
        native_min_value=0,
        native_max_value=95,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    CompitParameter.BOILER_TARGET_TEMPERATURE_CONST: NumberEntityDescription(
        key=CompitParameter.BOILER_TARGET_TEMPERATURE_CONST.value,
        translation_key="boiler_target_temperature_const",
        native_min_value=0,
        native_max_value=90,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
}


DEVICE_DEFINITIONS: dict[int, CompitDeviceDescription] = {
    7: CompitDeviceDescription(
        name="Nano One",
        parameters=[
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_COMFORT],
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_ECO],
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_HOLIDAY],
        ],
    ),
    12: CompitDeviceDescription(
        name="Nano Color",
        parameters=[
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_COMFORT],
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_ECO_WINTER],
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_ECO_COOLING],
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_OUT_OF_HOME],
        ],
    ),
    223: CompitDeviceDescription(
        name="Nano Color 2",
        parameters=[
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_COMFORT],
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_ECO_WINTER],
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_ECO_COOLING],
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_OUT_OF_HOME],
        ],
    ),
    3: CompitDeviceDescription(
        name="R810",
        parameters=[
            DESCRIPTIONS[CompitParameter.TARGET_TEMPERATURE_CONST],
        ],
    ),
    34: CompitDeviceDescription(
        name="r470",
        parameters=[
            DESCRIPTIONS[CompitParameter.HEATING_TARGET_TEMPERATURE_CONST],
        ],
    ),
    221: CompitDeviceDescription(
        name="R350.M",
        parameters=[
            DESCRIPTIONS[CompitParameter.MIXER_TARGET_TEMPERATURE],
        ],
    ),
    91: CompitDeviceDescription(
        name="R770RS / R771RS",
        parameters=[
            DESCRIPTIONS[CompitParameter.MIXER1_TARGET_TEMPERATURE],
            DESCRIPTIONS[CompitParameter.MIXER2_TARGET_TEMPERATURE],
        ],
    ),
    212: CompitDeviceDescription(
        name="BioMax742",
        parameters=[
            DESCRIPTIONS[CompitParameter.BOILER_TARGET_TEMPERATURE],
        ],
    ),
    210: CompitDeviceDescription(
        name="EL750",
        parameters=[
            DESCRIPTIONS[CompitParameter.BOILER_TARGET_TEMPERATURE],
        ],
    ),
    36: CompitDeviceDescription(
        name="BioMax742",
        parameters=[
            DESCRIPTIONS[CompitParameter.BOILER_TARGET_TEMPERATURE_CONST],
        ],
    ),
    75: CompitDeviceDescription(
        name="BioMax772",
        parameters=[
            DESCRIPTIONS[CompitParameter.BOILER_TARGET_TEMPERATURE_CONST],
        ],
    ),
    201: CompitDeviceDescription(
        name="BioMax775",
        parameters=[
            DESCRIPTIONS[CompitParameter.BOILER_TARGET_TEMPERATURE_CONST],
        ],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Compit number entities from a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        CompitNumber(
            coordinator,
            device_id,
            device_definition.name,
            entity_description,
        )
        for device_id, device in coordinator.connector.all_devices.items()
        if (device_definition := DEVICE_DEFINITIONS.get(device.definition.code))
        for entity_description in device_definition.parameters
    )


class CompitNumber(CoordinatorEntity[CompitDataUpdateCoordinator], NumberEntity):
    """Representation of a Compit number entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device_id: int,
        device_name: str,
        entity_description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device_name,
            manufacturer=MANUFACTURER_NAME,
            model=device_name,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.connector.get_device(self.device_id) is not None
        )

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.coordinator.connector.get_current_value(
            self.device_id, CompitParameter(self.entity_description.key)
        )
        if value is None or isinstance(value, str):
            return None
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.connector.set_device_parameter(
            self.device_id, CompitParameter(self.entity_description.key), value
        )
        self.async_write_ha_state()
