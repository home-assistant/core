"""Support for humidifiers."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import CLIMATE

from homeassistant.components.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitSerialBridge


class HumidifierComelitMode(StrEnum):
    """Serial Bridge humidifier modes."""

    AUTO = "A"
    OFF = "O"
    LOWER = "L"
    UPPER = "U"


class HumidifierComelitCommand(StrEnum):
    """Serial Bridge humidifier commands."""

    OFF = "off"
    ON = "on"
    MANUAL = "man"
    SET = "set"
    AUTO = "auto"
    LOWER = "lower"
    UPPER = "upper"


MODE_TO_ACTION: dict[str, HumidifierComelitCommand] = {
    MODE_AUTO: HumidifierComelitCommand.AUTO,
    MODE_NORMAL: HumidifierComelitCommand.MANUAL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit humidifiers."""

    coordinator: ComelitSerialBridge = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ComelitHumidifierEntity] = []
    for device in coordinator.data[CLIMATE].values():
        entities.append(
            ComelitHumidifierEntity(
                coordinator,
                device,
                config_entry.entry_id,
                active_mode=HumidifierComelitMode.LOWER,
                active_action=HumidifierAction.DRYING,
                set_command=HumidifierComelitCommand.LOWER,
                device_class=HumidifierDeviceClass.DEHUMIDIFIER,
            )
        )
        entities.append(
            ComelitHumidifierEntity(
                coordinator,
                device,
                config_entry.entry_id,
                active_mode=HumidifierComelitMode.UPPER,
                active_action=HumidifierAction.HUMIDIFYING,
                set_command=HumidifierComelitCommand.UPPER,
                device_class=HumidifierDeviceClass.HUMIDIFIER,
            ),
        )

    async_add_entities(entities)


class ComelitHumidifierEntity(CoordinatorEntity[ComelitSerialBridge], HumidifierEntity):
    """Humidifier device."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_available_modes = [MODE_NORMAL, MODE_AUTO]
    _attr_min_humidity = 10
    _attr_max_humidity = 90
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
        active_mode: HumidifierComelitMode,
        active_action: HumidifierAction,
        set_command: HumidifierComelitCommand,
        device_class: HumidifierDeviceClass,
    ) -> None:
        """Init light entity."""
        self._api = coordinator.api
        self._device = device
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}-{device_class}"
        self._attr_device_info = coordinator.platform_device_info(device, device_class)
        self._attr_device_class = device_class
        self._attr_translation_key = device_class.value
        self._active_mode = active_mode
        self._active_action = active_action
        self._set_command = set_command

    @property
    def _humidifier(self) -> list[Any]:
        """Return humidifier device data."""
        # CLIMATE has a 2 item tuple:
        # - first  for Clima
        # - second for Humidifier
        return self.coordinator.data[CLIMATE][self._device.index].val[1]

    @property
    def _api_mode(self) -> str:
        """Return device mode."""
        # Values from API: "O", "L", "U"
        return self._humidifier[2]

    @property
    def _api_active(self) -> bool:
        "Return device active/idle."
        return self._humidifier[1]

    @property
    def _api_automatic(self) -> bool:
        """Return device in automatic/manual mode."""
        return self._humidifier[3] == HumidifierComelitMode.AUTO

    @property
    def target_humidity(self) -> float:
        """Set target humidity."""
        return self._humidifier[4] / 10

    @property
    def current_humidity(self) -> float:
        """Return current humidity."""
        return self._humidifier[0] / 10

    @property
    def is_on(self) -> bool | None:
        """Return true is humidifier is on."""
        return self._api_mode == self._active_mode

    @property
    def mode(self) -> str | None:
        """Return current mode."""
        return MODE_AUTO if self._api_automatic else MODE_NORMAL

    @property
    def action(self) -> HumidifierAction | None:
        """Return current action."""

        if self._api_mode == HumidifierComelitMode.OFF:
            return HumidifierAction.OFF

        if self._api_active and self._api_mode == self._active_mode:
            return self._active_action

        return HumidifierAction.IDLE

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if self.mode == HumidifierComelitMode.OFF:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="humidity_while_off",
            )

        await self.coordinator.api.set_humidity_status(
            self._device.index, HumidifierComelitCommand.MANUAL
        )
        await self.coordinator.api.set_humidity_status(
            self._device.index, HumidifierComelitCommand.SET, humidity
        )

    async def async_set_mode(self, mode: str) -> None:
        """Set humidifier mode."""
        await self.coordinator.api.set_humidity_status(
            self._device.index, MODE_TO_ACTION[mode]
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.coordinator.api.set_humidity_status(
            self._device.index, self._set_command
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.coordinator.api.set_humidity_status(
            self._device.index, HumidifierComelitCommand.OFF
        )
