"""The Flexit Nordic (BACnet) integration fans."""

import asyncio
import asyncio.exceptions
from dataclasses import dataclass
from enum import StrEnum

from flexit_bacnet.bacnet import DecodingError

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FlexitDataUpdateCoordinator
from .const import DOMAIN, MANUFACTURER, MAX_FAN_SPEED, MIN_FAN_SPEED, MODEL, NAME


class FanFunction(StrEnum):
    """Fan function enum."""

    SUPPLY = "supply"
    EXTRACT = "extract"


class FanMode(StrEnum):
    """Fan mode enum."""

    AWAY = "away"
    HOME = "home"
    HIGH = "high"
    COOKER_HOOD = "cooker_hood"
    FIREPLACE = "fireplace"


@dataclass
class FlexitFanRequiredKeysMixin:
    """Required keys for the entity."""

    fan_mode: FanMode
    fan_function: FanFunction


# Finish this and use FanEntityDescription class here as well to clean up the code.
@dataclass
class FlexitFanEntityDescription(FanEntityDescription, FlexitFanRequiredKeysMixin):
    """Describes fan entity."""


FANS: tuple[FlexitFanEntityDescription, ...] = (
    FlexitFanEntityDescription(
        key="away_supply_fan",
        translation_key="away_supply_fan",
        name="away supply fan",
        fan_mode=FanMode.AWAY,
        fan_function=FanFunction.SUPPLY,
    ),
    FlexitFanEntityDescription(
        key="away_extract_fan",
        translation_key="away_extract_fan",
        name="away extract fan",
        fan_mode=FanMode.AWAY,
        fan_function=FanFunction.EXTRACT,
    ),
    FlexitFanEntityDescription(
        key="home_supply_fan",
        translation_key="home_supply_fan",
        name="home supply fan",
        fan_mode=FanMode.HOME,
        fan_function=FanFunction.SUPPLY,
    ),
    FlexitFanEntityDescription(
        key="home_extract_fan",
        translation_key="home_extract_fan",
        name="home extract fan",
        fan_mode=FanMode.HOME,
        fan_function=FanFunction.EXTRACT,
    ),
    FlexitFanEntityDescription(
        key="high_supply_fan",
        translation_key="high_supply_fan",
        name="high supply fan",
        fan_mode=FanMode.HIGH,
        fan_function=FanFunction.SUPPLY,
    ),
    FlexitFanEntityDescription(
        key="high_extract_fan",
        translation_key="high_extract_fan",
        name="high extract fan",
        fan_mode=FanMode.HIGH,
        fan_function=FanFunction.EXTRACT,
    ),
    FlexitFanEntityDescription(
        key="cooker_hood_supply_fan",
        translation_key="cooker_hood_supply_fan",
        name="cooker hood supply fan",
        fan_mode=FanMode.COOKER_HOOD,
        fan_function=FanFunction.SUPPLY,
    ),
    FlexitFanEntityDescription(
        key="cooker_hood_extract_fan",
        translation_key="cooker_hood_extract_fan",
        name="cooker hood extract fan",
        fan_mode=FanMode.COOKER_HOOD,
        fan_function=FanFunction.EXTRACT,
    ),
    FlexitFanEntityDescription(
        key="fireplace_supply_fan",
        translation_key="fireplace_supply_fan",
        name="fireplace supply fan",
        fan_mode=FanMode.FIREPLACE,
        fan_function=FanFunction.SUPPLY,
    ),
    FlexitFanEntityDescription(
        key="fireplace_extract_fan",
        translation_key="fireplace_extract_fan",
        name="fireplace extract fan",
        fan_mode=FanMode.FIREPLACE,
        fan_function=FanFunction.EXTRACT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flexit Nordic supply and extract air fans."""
    data_coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [FlexitFanEntity(data_coordinator, description) for description in FANS]
    async_add_entities(entities)


class FlexitFanEntity(CoordinatorEntity, FanEntity):
    """Flexit Nordic ventilation machine fan entity."""

    entity_description: FlexitFanEntityDescription
    _attr_has_entity_name = True
    _attr_supported_features = FanEntityFeature.SET_SPEED

    def __init__(
        self,
        coordinator: FlexitDataUpdateCoordinator,
        entity_description: FlexitFanEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.flexit_bacnet.serial_number}_{entity_description.key}"
        )

        self._flexit_bacnet = coordinator.flexit_bacnet
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.flexit_bacnet.serial_number),
            },
            name=NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def percentage(self) -> int | None:
        """Retrieve speed percentage of the fan."""
        match self.entity_description.fan_function:
            case FanFunction.SUPPLY:
                return self._get_supply_fan_percentage()
            case FanFunction.EXTRACT:
                return self._get_extract_fan_percentage()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        try:
            match self.entity_description.fan_function:
                case FanFunction.SUPPLY:
                    await self._set_supply_fan_percentage(percentage)
                case FanFunction.EXTRACT:
                    await self._set_extract_fan_percentage(percentage)
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    def _get_supply_fan_percentage(self) -> int:
        match self.entity_description.fan_mode:
            case FanMode.AWAY:
                return self._flexit_bacnet.fan_setpoint_supply_air_away
            case FanMode.HOME:
                return self._flexit_bacnet.fan_setpoint_supply_air_home
            case FanMode.HIGH:
                return self._flexit_bacnet.fan_setpoint_supply_air_high
            case FanMode.COOKER_HOOD:
                return self._flexit_bacnet.fan_setpoint_supply_air_cooker
            case FanMode.FIREPLACE:
                return self._flexit_bacnet.fan_setpoint_supply_air_fire

    def _get_extract_fan_percentage(self) -> int:
        match self.entity_description.fan_mode:
            case FanMode.AWAY:
                return self._flexit_bacnet.fan_setpoint_extract_air_away
            case FanMode.HOME:
                return self._flexit_bacnet.fan_setpoint_extract_air_home
            case FanMode.HIGH:
                return self._flexit_bacnet.fan_setpoint_extract_air_high
            case FanMode.COOKER_HOOD:
                return self._flexit_bacnet.fan_setpoint_extract_air_cooker
            case FanMode.FIREPLACE:
                return self._flexit_bacnet.fan_setpoint_extract_air_fire

    async def _set_supply_fan_percentage(self, percentage: int) -> None:
        try:
            match self.entity_description.fan_mode:
                case FanMode.AWAY:
                    max_percentage = self._flexit_bacnet.fan_setpoint_supply_air_home
                    percentage = self._clamp(percentage, MIN_FAN_SPEED, max_percentage)
                    await self._flexit_bacnet.set_fan_setpoint_supply_air_away(
                        percentage
                    )
                case FanMode.HOME:
                    min_percentage = self._flexit_bacnet.fan_setpoint_supply_air_away
                    max_percentage = self._flexit_bacnet.fan_setpoint_supply_air_high
                    percentage = self._clamp(percentage, min_percentage, max_percentage)
                    await self._flexit_bacnet.set_fan_setpoint_supply_air_home(
                        percentage
                    )
                case FanMode.HIGH:
                    min_percentage = self._flexit_bacnet.fan_setpoint_supply_air_home
                    percentage = self._clamp(percentage, min_percentage, MAX_FAN_SPEED)
                    await self._flexit_bacnet.set_fan_setpoint_supply_air_high(
                        percentage
                    )
                case FanMode.COOKER_HOOD:
                    percentage = self._clamp(percentage, MIN_FAN_SPEED, MAX_FAN_SPEED)
                    await self._flexit_bacnet.set_fan_setpoint_supply_air_cooker(
                        percentage
                    )
                case FanMode.FIREPLACE:
                    percentage = self._clamp(percentage, MIN_FAN_SPEED, MAX_FAN_SPEED)
                    await self._flexit_bacnet.set_fan_setpoint_supply_air_fire(
                        percentage
                    )
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    async def _set_extract_fan_percentage(self, percentage: int) -> None:
        try:
            match self.entity_description.fan_mode:
                case FanMode.AWAY:
                    max_percentage = self._flexit_bacnet.fan_setpoint_extract_air_home
                    percentage = self._clamp(percentage, MIN_FAN_SPEED, max_percentage)
                    await self._flexit_bacnet.set_fan_setpoint_extract_air_away(
                        percentage
                    )
                case FanMode.HOME:
                    min_percentage = self._flexit_bacnet.fan_setpoint_extract_air_away
                    max_percentage = self._flexit_bacnet.fan_setpoint_extract_air_high
                    percentage = self._clamp(percentage, min_percentage, max_percentage)
                    await self._flexit_bacnet.set_fan_setpoint_extract_air_home(
                        percentage
                    )
                case FanMode.HIGH:
                    min_percentage = self._flexit_bacnet.fan_setpoint_extract_air_home
                    percentage = self._clamp(percentage, min_percentage, MAX_FAN_SPEED)
                    await self._flexit_bacnet.set_fan_setpoint_extract_air_high(
                        percentage
                    )
                case FanMode.COOKER_HOOD:
                    percentage = self._clamp(percentage, MIN_FAN_SPEED, MAX_FAN_SPEED)
                    await self._flexit_bacnet.set_fan_setpoint_extract_air_cooker(
                        percentage
                    )
                case FanMode.FIREPLACE:
                    percentage = self._clamp(percentage, MIN_FAN_SPEED, MAX_FAN_SPEED)
                    await self._flexit_bacnet.set_fan_setpoint_extract_air_fire(
                        percentage
                    )
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    def _clamp(self, percentage: int, min_percentage: int, max_percentage: int) -> int:
        return max(min(percentage, max_percentage), min_percentage)
