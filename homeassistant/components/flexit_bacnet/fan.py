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

    HOME = "home"
    AWAY = "away"
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
            FlexitFanEntity(device, FanMode.AWAY, FanFunction.SUPPLY, 30, 73),
            FlexitFanEntity(device, FanMode.AWAY, FanFunction.EXTRACT, 30, 66),
            FlexitFanEntity(device, FanMode.HOME, FanFunction.SUPPLY, 30, 75),
            FlexitFanEntity(device, FanMode.HOME, FanFunction.EXTRACT, 60, 100),
            FlexitFanEntity(device, FanMode.HIGH, FanFunction.SUPPLY, 73, 100),
            FlexitFanEntity(device, FanMode.HIGH, FanFunction.EXTRACT, 66, 100),
            FlexitFanEntity(device, FanMode.COOKER_HOOD, FanFunction.SUPPLY, 30, 100),
            FlexitFanEntity(device, FanMode.COOKER_HOOD, FanFunction.EXTRACT, 66, 100),
            FlexitFanEntity(device, FanMode.FIREPLACE, FanFunction.SUPPLY, 30, 100),
            FlexitFanEntity(device, FanMode.FIREPLACE, FanFunction.EXTRACT, 30, 100),
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
        min_percentage: int,
        max_percentage: int,
    ) -> None:
        """Initialize the entity."""
        self._device = device
        self._fan_function = fan_function
        self._fan_mode = fan_mode
        self._min_percentage = min_percentage
        self._max_percentage = max_percentage
        self._attr_unique_id = f"{device.serial_number}.{fan_function}.{fan_mode}.fan"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device.serial_number),
            },
            name="Ventilation",
            manufacturer="Flexit",
            model="Nordic",
        )

    async def async_update(self) -> None:
        """Refresh unit state."""
        await self._device.update()

    @property
    def name(self) -> str:
        """Name of the entity."""
        return f"{self._device.device_name}.{self._fan_function}.{self._fan_mode}"

    @property
    def percentage(self) -> int | None:
        """Retrieve percentage of the fan speed."""
        match self._fan_function:
            case FanFunction.SUPPLY:
                return self._get_supply_fan_percentage()
            case FanFunction.EXTRACT:
                return self._get_extract_fan_percentage()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        percentage = max(min(self._max_percentage, percentage), self._min_percentage)
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
            case FanMode.HOME:
                return self._device.fan_setpoint_supply_air_home
            case FanMode.AWAY:
                return self._device.fan_setpoint_supply_air_away
            case FanMode.HIGH:
                return self._device.fan_setpoint_supply_air_high
            case FanMode.COOKER_HOOD:
                return self._device.fan_setpoint_supply_air_cooker
            case FanMode.FIREPLACE:
                return self._device.fan_setpoint_supply_air_fire

    def _get_extract_fan_percentage(self) -> int:
        match self._fan_mode:
            case FanMode.HOME:
                return self._device.fan_setpoint_extract_air_home
            case FanMode.AWAY:
                return self._device.fan_setpoint_extract_air_away
            case FanMode.HIGH:
                return self._device.fan_setpoint_extract_air_high
            case FanMode.COOKER_HOOD:
                return self._device.fan_setpoint_extract_air_cooker
            case FanMode.FIREPLACE:
                return self._device.fan_setpoint_extract_air_fire

    async def _set_supply_fan_percentage(self, percentage: int) -> None:
        try:
            match self._fan_mode:
                case FanMode.HOME:
                    await self._device.set_fan_setpoint_supply_air_home(percentage)
                case FanMode.AWAY:
                    await self._device.set_fan_setpoint_supply_air_away(percentage)
                case FanMode.HIGH:
                    await self._device.set_fan_setpoint_supply_air_high(percentage)
                case FanMode.COOKER_HOOD:
                    await self._device.set_fan_setpoint_supply_air_cooker(percentage)
                case FanMode.FIREPLACE:
                    await self._device.set_fan_setpoint_supply_air_fire(percentage)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    async def _set_extract_fan_percentage(self, percentage: int) -> None:
        try:
            match self._fan_mode:
                case FanMode.HOME:
                    await self._device.set_fan_setpoint_extract_air_home(percentage)
                case FanMode.AWAY:
                    await self._device.set_fan_setpoint_extract_air_away(percentage)
                case FanMode.HIGH:
                    await self._device.set_fan_setpoint_extract_air_high(percentage)
                case FanMode.COOKER_HOOD:
                    await self._device.set_fan_setpoint_extract_air_cooker(percentage)
                case FanMode.FIREPLACE:
                    await self._device.set_fan_setpoint_extract_air_fire(percentage)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc
