"""Fan platform for Prana integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PranaFanType, PranaSwitchType
from .coordinator import PranaCoordinator
from .switch import PranaSendSwitch

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


class PranaSendSpeed:
    """Helper to send speed-related commands to the device."""

    def __init__(self, fan_type: str, coordinator: PranaCoordinator) -> None:
        """Initialize command helper."""
        self.fan_type = fan_type
        self.coordinator = coordinator

    async def send_speed_percentage(self, percentage: int) -> None:
        """Send a speed percentage command to the device."""
        _LOGGER.debug(
            "Setting speed percentage to %s for fan type %s (max=%s)",
            percentage,
            self.fan_type,
            self.coordinator.max_speed,
        )
        effective_type = (
            PranaFanType.BOUNDED
            if self.coordinator.data.get("bound")
            else self.fan_type
        )
        max_speed = self.coordinator.max_speed or 10
        speed = percentage // (100 // max_speed)
        _LOGGER.debug(
            "Calculated device speed: %s for percentage: %s", speed, percentage
        )
        try:
            await self.coordinator.api_client.set_speed(
                speed=speed * 10, fan_type=effective_type
            )
        except Exception as err:
            raise HomeAssistantError(f"Error setting speed: {err}") from err

    async def send_speed_is_on(self, value: bool) -> None:
        """Send a command to toggle fan power state."""
        effective_type = (
            PranaFanType.BOUNDED
            if self.coordinator.data.get("bound")
            else self.fan_type
        )
        try:
            await self.coordinator.api_client.set_speed_is_on(
                speed_is_on=value, fan_type=effective_type
            )
        except Exception as err:
            raise HomeAssistantError(f"Error setting speed is_on: {err}") from err


class PranaFan(FanEntity):
    """Representation of a Prana fan entity (extract, supply, bounded)."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.PRESET_MODE
    )
    _attr_unique_id: str

    def __init__(
        self,
        unique_id: str,
        coordinator: PranaCoordinator,
        fan_type: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the fan entity."""
        self._attr_unique_id = unique_id
        self.coordinator = coordinator
        self._attr_is_on = False
        self._attr_percentage = 0
        self.fan_type = fan_type
        self._attr_preset_modes = ["Night", "Boost"]
        if self.fan_type == PranaFanType.EXTRACT:
            self._attr_translation_key = "extract_speed"
        elif self.fan_type == PranaFanType.SUPPLY:
            self._attr_translation_key = "supply_speed"
        elif self.fan_type == PranaFanType.BOUNDED:
            self._attr_translation_key = "bounded_speed"
        else:
            self._attr_translation_key = "fan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name", "Prana Device"),
            manufacturer="Prana",
            model="PRANA RECUPERATOR",
        )
        self._attr_icon = self.get_icon()

    def get_icon(self) -> str:
        """Return an icon representing the fan type."""
        if self.fan_type == PranaFanType.EXTRACT:
            return "mdi:arrow-expand-right"
        if self.fan_type == PranaFanType.SUPPLY:
            return "mdi:arrow-expand-left"
        if self.fan_type == PranaFanType.BOUNDED:
            return "mdi:arrow-expand-horizontal"
        return "mdi:help"

    @property
    def is_on(self) -> bool:
        """Return True if the fan reports it is on."""
        if self.coordinator.data:
            return self.coordinator.data.get(self.fan_type, {}).get("is_on", False)
        return False

    @property
    def speed_count(self) -> int:
        """Return total number of speed steps."""
        return self.coordinator.data.get(self.fan_type, {}).get("max_speed", 10)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Handle preset mode selection by mapping to switches."""
        send_switch = None
        if preset_mode == "Night":
            send_switch = PranaSendSwitch(
                True, PranaSwitchType.NIGHT, coordinator=self.coordinator
            )
        elif preset_mode == "Boost":
            send_switch = PranaSendSwitch(
                True, PranaSwitchType.BOOST, coordinator=self.coordinator
            )
        if send_switch:
            await send_switch.send()
            await self.coordinator.async_refresh()
            self.async_write_ha_state()

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage (0-100)."""
        max_speed = self.coordinator.max_speed or 10
        if self.coordinator.data:
            original_speed = self.coordinator.data.get(self.fan_type, {}).get("speed")
            if original_speed is None:
                return None
            speed = original_speed * (100 // max_speed)
            if speed > 100:
                return 100
            return speed
        return None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        self._attr_is_on = True
        sender = PranaSendSpeed(self.fan_type, self.coordinator)
        await sender.send_speed_is_on(True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._attr_is_on = False
        sender = PranaSendSpeed(self.fan_type, self.coordinator)
        await sender.send_speed_is_on(False)
        await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """Register update listener when entity is added."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed as a percentage."""
        sender = PranaSendSpeed(self.fan_type, self.coordinator)
        await sender.send_speed_percentage(percentage)
        await self.coordinator.async_refresh()
        self._attr_percentage = percentage
        self._attr_is_on = percentage > 0
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity availability based on coordinator success."""
        return self.coordinator.last_update_success


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana fan entities from a config entry."""
    _LOGGER.info("Setting up Prana fan entities")
    coordinator: PranaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PranaFan(
                unique_id=f"{entry.entry_id}-extractfan",
                coordinator=coordinator,
                fan_type=PranaFanType.EXTRACT,
                entry=entry,
            ),
            PranaFan(
                unique_id=f"{entry.entry_id}-supplyfan",
                coordinator=coordinator,
                fan_type=PranaFanType.SUPPLY,
                entry=entry,
            ),
        ]
    )
