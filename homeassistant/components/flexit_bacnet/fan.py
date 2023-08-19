"""The Flexit Nordic (BACnet) integration fans."""

import asyncio
import asyncio.exceptions
from enum import StrEnum

from flexit_bacnet import FlexitBACnet
from flexit_bacnet.bacnet import DecodingError

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the Flexit Nordic supply and extract air fans."""
    device = hass.data[DOMAIN][config_entry.entry_id]

    async_add_devices(
        [
            FlexitFanEntity(device, FanMode.AWAY, FanFunction.SUPPLY),
            FlexitFanEntity(device, FanMode.AWAY, FanFunction.EXTRACT),
            FlexitFanEntity(device, FanMode.HOME, FanFunction.SUPPLY),
            FlexitFanEntity(device, FanMode.HOME, FanFunction.EXTRACT),
            FlexitFanEntity(device, FanMode.HIGH, FanFunction.SUPPLY),
            FlexitFanEntity(device, FanMode.HIGH, FanFunction.EXTRACT),
            FlexitFanEntity(device, FanMode.COOKER_HOOD, FanFunction.SUPPLY),
            FlexitFanEntity(device, FanMode.COOKER_HOOD, FanFunction.EXTRACT),
            FlexitFanEntity(device, FanMode.FIREPLACE, FanFunction.SUPPLY),
            FlexitFanEntity(device, FanMode.FIREPLACE, FanFunction.EXTRACT),
        ]
    )


class FlexitFanEntity(FanEntity):
    """Flexit air intake fan."""

    _attr_has_entity_name = True
    _attr_supported_features = FanEntityFeature.SET_SPEED

    def __init__(
        self,
        device: FlexitBACnet,
        fan_mode: FanMode,
        fan_function: FanFunction,
    ) -> None:
        """Initialize the entity."""
        self._device = device
        self._fan_function = fan_function
        self._fan_mode = fan_mode
        self._attr_unique_id = f"{device.serial_number}.{fan_mode}.{fan_function}.fan"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device.serial_number),
            },
            name="Fan",
            manufacturer="Flexit",
            model="Nordic",
        )

    async def async_update(self) -> None:
        """Refresh unit state."""

    @property
    def name(self) -> str:
        """Name of the entity."""
        return f"{self._device.device_name}.{self._fan_mode}.{self._fan_function}"

    @property
    def percentage(self) -> int | None:
        """Retrieve speed percentage of the fan."""
        match self._fan_function:
            case FanFunction.SUPPLY:
                return self._get_supply_fan_percentage()
            case FanFunction.EXTRACT:
                return self._get_extract_fan_percentage()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        try:
            match self._fan_function:
                case FanFunction.SUPPLY:
                    await self._set_supply_fan_percentage(percentage)
                case FanFunction.EXTRACT:
                    await self._set_extract_fan_percentage(percentage)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    def _get_supply_fan_percentage(self) -> int:
        match self._fan_mode:
            case FanMode.AWAY:
                return self._device.fan_setpoint_supply_air_away
            case FanMode.HOME:
                return self._device.fan_setpoint_supply_air_home
            case FanMode.HIGH:
                return self._device.fan_setpoint_supply_air_high
            case FanMode.COOKER_HOOD:
                return self._device.fan_setpoint_supply_air_cooker
            case FanMode.FIREPLACE:
                return self._device.fan_setpoint_supply_air_fire

    def _get_extract_fan_percentage(self) -> int:
        match self._fan_mode:
            case FanMode.AWAY:
                return self._device.fan_setpoint_extract_air_away
            case FanMode.HOME:
                return self._device.fan_setpoint_extract_air_home
            case FanMode.HIGH:
                return self._device.fan_setpoint_extract_air_high
            case FanMode.COOKER_HOOD:
                return self._device.fan_setpoint_extract_air_cooker
            case FanMode.FIREPLACE:
                return self._device.fan_setpoint_extract_air_fire

    async def _set_supply_fan_percentage(self, percentage: int) -> None:
        try:
            match self._fan_mode:
                case FanMode.AWAY:
                    max_percentage = self._device.fan_setpoint_supply_air_home
                    percentage = self._clamp(percentage, 30, max_percentage)
                    await self._device.set_fan_setpoint_supply_air_away(percentage)
                case FanMode.HOME:
                    min_percentage = self._device.fan_setpoint_supply_air_away
                    max_percentage = self._device.fan_setpoint_supply_air_high
                    percentage = self._clamp(percentage, min_percentage, max_percentage)
                    await self._device.set_fan_setpoint_supply_air_home(percentage)
                case FanMode.HIGH:
                    min_percentage = self._device.fan_setpoint_supply_air_home
                    percentage = self._clamp(percentage, min_percentage, 100)
                    await self._device.set_fan_setpoint_supply_air_high(percentage)
                case FanMode.COOKER_HOOD:
                    percentage = self._clamp(percentage, 30, 100)
                    await self._device.set_fan_setpoint_supply_air_cooker(percentage)
                case FanMode.FIREPLACE:
                    percentage = self._clamp(percentage, 30, 100)
                    await self._device.set_fan_setpoint_supply_air_fire(percentage)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    async def _set_extract_fan_percentage(self, percentage: int) -> None:
        try:
            match self._fan_mode:
                case FanMode.AWAY:
                    max_percentage = self._device.fan_setpoint_extract_air_home
                    percentage = self._clamp(percentage, 30, max_percentage)
                    await self._device.set_fan_setpoint_extract_air_away(percentage)
                case FanMode.HOME:
                    min_percentage = self._device.fan_setpoint_extract_air_away
                    max_percentage = self._device.fan_setpoint_extract_air_high
                    percentage = self._clamp(percentage, min_percentage, max_percentage)
                    await self._device.set_fan_setpoint_extract_air_home(percentage)
                case FanMode.HIGH:
                    min_percentage = self._device.fan_setpoint_extract_air_home
                    percentage = self._clamp(percentage, min_percentage, 100)
                    await self._device.set_fan_setpoint_extract_air_high(percentage)
                case FanMode.COOKER_HOOD:
                    percentage = self._clamp(percentage, 30, 100)
                    await self._device.set_fan_setpoint_extract_air_cooker(percentage)
                case FanMode.FIREPLACE:
                    percentage = self._clamp(percentage, 30, 100)
                    await self._device.set_fan_setpoint_extract_air_fire(percentage)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    def _clamp(self, percentage: int, min_percentage: int, max_percentage: int) -> int:
        return max(min(percentage, max_percentage), min_percentage)
