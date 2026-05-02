"""Water heater platform for Compit integration."""

from dataclasses import dataclass
from typing import Any

from compit_inext_api.consts import CompitParameter
from propcache.api import cached_property

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_OFF,
    STATE_ON,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

PARALLEL_UPDATES = 0
STATE_SCHEDULE = "schedule"
COMPIT_STATE_TO_HA = {
    STATE_OFF: STATE_OFF,
    STATE_ON: STATE_PERFORMANCE,
    STATE_SCHEDULE: STATE_ECO,
}
HA_STATE_TO_COMPIT = {value: key for key, value in COMPIT_STATE_TO_HA.items()}


@dataclass(frozen=True, kw_only=True)
class CompitWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    """Class to describe a Compit water heater device."""

    min_temp: float
    max_temp: float
    supported_features: WaterHeaterEntityFeature
    supports_current_temperature: bool = True


DEVICE_DEFINITIONS: dict[int, CompitWaterHeaterEntityDescription] = {
    34: CompitWaterHeaterEntityDescription(
        key="r470",
        min_temp=0.0,
        max_temp=75.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    91: CompitWaterHeaterEntityDescription(
        key="R770RS / R771RS",
        min_temp=30.0,
        max_temp=80.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    92: CompitWaterHeaterEntityDescription(
        key="r490",
        min_temp=30.0,
        max_temp=80.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    215: CompitWaterHeaterEntityDescription(
        key="R480",
        min_temp=30.0,
        max_temp=80.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    222: CompitWaterHeaterEntityDescription(
        key="R377B",
        min_temp=30.0,
        max_temp=75.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    224: CompitWaterHeaterEntityDescription(
        key="R 900",
        min_temp=0.0,
        max_temp=70.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    36: CompitWaterHeaterEntityDescription(
        key="BioMax742",
        min_temp=0.0,
        max_temp=75.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    75: CompitWaterHeaterEntityDescription(
        key="BioMax772",
        min_temp=0.0,
        max_temp=75.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    201: CompitWaterHeaterEntityDescription(
        key="BioMax775",
        min_temp=0.0,
        max_temp=75.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    210: CompitWaterHeaterEntityDescription(
        key="EL750",
        min_temp=30.0,
        max_temp=80.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE,
    ),
    44: CompitWaterHeaterEntityDescription(
        key="SolarComp 951",
        min_temp=0.0,
        max_temp=85.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE,
        supports_current_temperature=False,
    ),
    45: CompitWaterHeaterEntityDescription(
        key="SolarComp971",
        min_temp=0.0,
        max_temp=75.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE,
        supports_current_temperature=False,
    ),
    99: CompitWaterHeaterEntityDescription(
        key="SolarComp971C",
        min_temp=0.0,
        max_temp=75.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE,
        supports_current_temperature=False,
    ),
    53: CompitWaterHeaterEntityDescription(
        key="R350.CWU",
        min_temp=0.0,
        max_temp=80.0,
        supported_features=WaterHeaterEntityFeature.TARGET_TEMPERATURE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Compit water heater entities from a config entry."""

    coordinator = entry.runtime_data
    async_add_entities(
        CompitWaterHeater(coordinator, device_id, entity_description)
        for device_id, device in coordinator.connector.all_devices.items()
        if (entity_description := DEVICE_DEFINITIONS.get(device.definition.code))
    )


class CompitWaterHeater(
    CoordinatorEntity[CompitDataUpdateCoordinator], WaterHeaterEntity
):
    """Representation of a Compit Water Heater."""

    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_name = None
    entity_description: CompitWaterHeaterEntityDescription

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device_id: int,
        entity_description: CompitWaterHeaterEntityDescription,
    ) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=entity_description.key,
            manufacturer=MANUFACTURER_NAME,
            model=entity_description.key,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.connector.get_device(self.device_id) is not None
        )

    @cached_property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.entity_description.min_temp

    @cached_property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.entity_description.max_temp

    @cached_property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the supported features."""
        return self.entity_description.supported_features

    @cached_property
    def operation_list(self) -> list[str] | None:
        """Return the list of available operation modes."""
        if (
            self.entity_description.supported_features
            & WaterHeaterEntityFeature.OPERATION_MODE
        ):
            return [STATE_OFF, STATE_PERFORMANCE, STATE_ECO]
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the set target temperature."""
        value = self.coordinator.connector.get_current_value(
            self.device_id, CompitParameter.DHW_TARGET_TEMPERATURE
        )

        if isinstance(value, float):
            return value

        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.entity_description.supports_current_temperature is False:
            return None

        value = self.coordinator.connector.get_current_value(
            self.device_id, CompitParameter.DHW_CURRENT_TEMPERATURE
        )

        if isinstance(value, float):
            return value

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            return

        self._attr_target_temperature = temperature

        await self.coordinator.connector.set_device_parameter(
            self.device_id,
            CompitParameter.DHW_TARGET_TEMPERATURE,
            float(temperature),
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        await self.coordinator.connector.select_device_option(
            self.device_id,
            CompitParameter.DHW_ON_OFF,
            HA_STATE_TO_COMPIT[STATE_PERFORMANCE],
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        await self.coordinator.connector.select_device_option(
            self.device_id,
            CompitParameter.DHW_ON_OFF,
            HA_STATE_TO_COMPIT[STATE_OFF],
        )
        self.async_write_ha_state()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        await self.coordinator.connector.select_device_option(
            self.device_id,
            CompitParameter.DHW_ON_OFF,
            HA_STATE_TO_COMPIT[operation_mode],
        )
        self.async_write_ha_state()

    @property
    def current_operation(self) -> str | None:
        """Return the current operation mode."""
        on_off = self.coordinator.connector.get_current_option(
            self.device_id, CompitParameter.DHW_ON_OFF
        )

        if on_off is None:
            return None

        return COMPIT_STATE_TO_HA.get(on_off)
