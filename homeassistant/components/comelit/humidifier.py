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


class HumidifierComelitAction(StrEnum):
    """Serial Bridge humidifier actions."""

    OFF = "off"
    ON = "on"
    MANUAL = "man"
    SET = "set"
    AUTO = "auto"
    LOWER = "lower"
    UPPER = "upper"


MODE_TO_ACTION: dict[str, HumidifierComelitAction] = {
    MODE_AUTO: HumidifierComelitAction.AUTO,
    MODE_NORMAL: HumidifierComelitAction.MANUAL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit humidifiers."""

    coordinator: ComelitSerialBridge = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ComelitHumidifierEntity] = []
    for device_class in (
        HumidifierDeviceClass.HUMIDIFIER,
        HumidifierDeviceClass.DEHUMIDIFIER,
    ):
        entities.extend(
            ComelitHumidifierEntity(
                coordinator, device, config_entry.entry_id, device_class.value
            )
            for device in coordinator.data[CLIMATE].values()
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
        device_class: str,
    ) -> None:
        """Init light entity."""
        self._api = coordinator.api
        self._device = device
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}-{device_class}"
        self._attr_name = f"{device_class.capitalize()}"
        self._attr_device_info = coordinator.platform_device_info(device, device_class)
        self._attr_device_class = (
            HumidifierDeviceClass.DEHUMIDIFIER
            if device_class == HumidifierDeviceClass.DEHUMIDIFIER.value
            else HumidifierDeviceClass.HUMIDIFIER
        )

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
    def _is_dehumidifier(self) -> bool:
        """Return true if device is set as dehumidifier."""
        return (
            self._api_mode == HumidifierComelitMode.LOWER
            and self._attr_device_class == HumidifierDeviceClass.DEHUMIDIFIER
        )

    @property
    def _is_humidifier(self) -> bool:
        """Return true if device is set as humidifier."""
        return (
            self._api_mode == HumidifierComelitMode.UPPER
            and self._attr_device_class == HumidifierDeviceClass.HUMIDIFIER
        )

    @property
    def target_humidity(self) -> int:
        """Set target humidity."""
        return self._humidifier[4] / 10

    @property
    def current_humidity(self) -> int:
        """Return current humidity."""
        return self._humidifier[0] / 10

    @property
    def is_on(self) -> bool | None:
        """Return true is humidifier is on."""
        return self._is_dehumidifier or self._is_humidifier

    @property
    def mode(self) -> str | None:
        """Return current mode."""
        return MODE_AUTO if self._api_automatic else MODE_NORMAL

    @property
    def action(self) -> HumidifierAction | None:
        """Return current action."""

        if self._api_mode == HumidifierComelitMode.OFF:
            return HumidifierAction.OFF

        if self._api_active and self._is_dehumidifier:
            return HumidifierAction.DRYING

        if self._api_active and self._is_humidifier:
            return HumidifierAction.HUMIDIFYING

        return HumidifierAction.IDLE

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if self.mode == HumidifierComelitMode.OFF:
            return

        await self.coordinator.api.set_humidity_status(
            self._device.index, HumidifierComelitAction.MANUAL
        )
        await self.coordinator.api.set_humidity_status(
            self._device.index, HumidifierComelitAction.SET, humidity
        )

    async def async_set_mode(self, mode: str) -> None:
        """Set humidifier mode."""
        await self.coordinator.api.set_humidity_status(
            self._device.index, MODE_TO_ACTION[mode]
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        mode = (
            HumidifierComelitAction.LOWER
            if self._attr_device_class == HumidifierDeviceClass.DEHUMIDIFIER
            else HumidifierComelitAction.UPPER
        )
        await self.coordinator.api.set_humidity_status(self._device.index, mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.coordinator.api.set_humidity_status(
            self._device.index, HumidifierComelitAction.OFF
        )
