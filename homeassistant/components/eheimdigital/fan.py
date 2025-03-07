"""EHEIM Digital fans."""

from typing import Any, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.types import EheimDigitalClientError, FilterMode

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EheimDigitalConfigEntry
from .const import FILTER_BIO_MODE, FILTER_PRESET_TO_FILTER_MODE, FILTER_PULSE_MODE
from .coordinator import EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the callbacks for the coordinator so fans can be added as devices are found."""

    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_address: str | dict[str, EheimDigitalDevice],
    ) -> None:
        """Set up the climate entities for one or multiple devices."""
        entities: list[EheimDigitalClassicVarioPump] = []
        if isinstance(device_address, str):
            device_address = {device_address: coordinator.hub.devices[device_address]}
        for device in device_address.values():
            if isinstance(device, EheimDigitalClassicVario):
                entities.append(EheimDigitalClassicVarioPump(coordinator, device))
                coordinator.known_devices.add(device.mac_address)

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)

    async_setup_device_entities(coordinator.hub.devices)


class EheimDigitalClassicVarioPump(
    EheimDigitalEntity[EheimDigitalClassicVario], FanEntity
):
    """Represent an EHEIM Digital filter pump."""

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = [FILTER_BIO_MODE, FILTER_PULSE_MODE]
    _attr_preset_mode: str | None = None
    _attr_translation_key = "filter"
    _attr_name = None

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: EheimDigitalClassicVario,
    ) -> None:
        """Initialize an EHEIM Digital classicVARIO light entity."""
        super().__init__(coordinator, device)
        self._attr_unique_id = self._device_address
        self._async_update_attrs()

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        try:
            if preset_mode in FILTER_PRESET_TO_FILTER_MODE:
                await self._device.set_filter_mode(
                    FILTER_PRESET_TO_FILTER_MODE[preset_mode]
                )
        except EheimDigitalClientError as err:
            raise HomeAssistantError from err

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the pump speed."""
        try:
            if self._device.filter_mode != FilterMode.MANUAL:
                await self._device.set_filter_mode(FilterMode.MANUAL)
            await self._device.set_manual_speed(percentage)
        except EheimDigitalClientError as err:
            raise HomeAssistantError from err

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            await self._device.set_active(active=True)
            if preset_mode and preset_mode in FILTER_PRESET_TO_FILTER_MODE:
                await self._device.set_filter_mode(
                    FILTER_PRESET_TO_FILTER_MODE[preset_mode]
                )
            elif percentage:
                await self._device.set_filter_mode(FilterMode.MANUAL)
                await self._device.set_manual_speed(percentage)
        except EheimDigitalClientError as err:
            raise HomeAssistantError from err

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self._device.set_active(active=False)
        except EheimDigitalClientError as err:
            raise HomeAssistantError from err

    @override
    def _async_update_attrs(self) -> None:
        self._attr_is_on = self._device.is_active
        self._attr_percentage = self._device.current_speed

        match self._device.filter_mode:
            case FilterMode.MANUAL:
                self._attr_preset_mode = None
            case FilterMode.BIO:
                self._attr_preset_mode = FILTER_BIO_MODE
            case FilterMode.PULSE:
                self._attr_preset_mode = FILTER_PULSE_MODE
