"""Support for humidifiers."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, cast

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ComelitConfigEntry, ComelitSerialBridge
from .entity import ComelitBridgeBaseEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


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
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit humidifiers."""

    coordinator = cast(ComelitSerialBridge, config_entry.runtime_data)

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


class ComelitHumidifierEntity(ComelitBridgeBaseEntity, HumidifierEntity):
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
        super().__init__(coordinator, device, config_entry_entry_id)
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}-{device_class}"
        self._attr_device_class = device_class
        self._attr_translation_key = device_class.value
        self._active_mode = active_mode
        self._active_action = active_action
        self._set_command = set_command
        self._update_attributes()

    def _update_attributes(self) -> None:
        """Update class attributes."""
        device = self.coordinator.data[CLIMATE][self._device.index]
        if not isinstance(device.val, list):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_clima_data"
            )

        # CLIMATE has a 2 item tuple:
        # - first  for Clima
        # - second for Humidifier
        values = device.val[1]

        _active = values[1]
        _mode = values[2]  # Values from API: "O", "L", "U"
        _automatic = values[3] == HumidifierComelitMode.AUTO

        self._attr_action = HumidifierAction.IDLE
        if _mode == HumidifierComelitMode.OFF:
            self._attr_action = HumidifierAction.OFF
        if _active and _mode == self._active_mode:
            self._attr_action = self._active_action

        self._attr_current_humidity = values[0] / 10
        self._attr_is_on = _mode == self._active_mode
        self._attr_mode = MODE_AUTO if _automatic else MODE_NORMAL
        self._attr_target_humidity = values[4] / 10

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if not self._attr_is_on:
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
        self._attr_target_humidity = humidity
        self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set humidifier mode."""
        await self.coordinator.api.set_humidity_status(
            self._device.index, MODE_TO_ACTION[mode]
        )
        self._attr_mode = mode
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.coordinator.api.set_humidity_status(
            self._device.index, self._set_command
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.coordinator.api.set_humidity_status(
            self._device.index, HumidifierComelitCommand.OFF
        )
        self._attr_is_on = False
        self.async_write_ha_state()
