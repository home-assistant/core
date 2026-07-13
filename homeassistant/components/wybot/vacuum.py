"""Platform for vacuum integration."""

import logging
from typing import Any, cast, override

from wybot.dp_models import (
    Battery,
    BatteryState,
    CleaningMode,
    CleaningStatus,
    CleaningStatusMode,
    Dock,
    DockConnectionStatus,
    DockStatus,
    GenericDP,
)
from wybot.models import Group

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WyBotConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import WyBotCoordinator

_LOGGER = logging.getLogger(__name__)

# Commands are issued over BLE/MQTT; serialize to avoid concurrent device writes.
PARALLEL_UPDATES = 1


def format_mac(mac: str) -> str:
    """Format a MAC address string with colons.

    Converts "CCBA97932A96" to "CC:BA:97:93:2A:96".
    """
    mac = mac.upper().replace(":", "").replace("-", "")
    return ":".join(mac[i : i + 2] for i in range(0, 12, 2))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WyBotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the vacuum platform."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        """Add vacuum entities for devices discovered after setup."""
        new_ids = [d for d in coordinator.vacuums if d not in known]
        known.update(new_ids)
        if new_ids:
            async_add_entities(
                WyBotVacuum(idx=device_id, coordinator=coordinator)
                for device_id in new_ids
            )

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class WyBotVacuum(StateVacuumEntity, CoordinatorEntity[WyBotCoordinator]):
    """A wybot vacuum."""

    # Primary entity of the device: take the device's name as the entity name.
    _attr_has_entity_name = True
    _attr_name = None

    _data: Group | None
    _idx: str
    _coordinator: WyBotCoordinator

    def __init__(self, idx: str, coordinator: WyBotCoordinator) -> None:
        """Initialize the WyBot vacuum entity."""
        super().__init__(coordinator=coordinator, context=idx)
        self._idx = idx
        self._coordinator = coordinator
        # Initialize data safely
        self._data = coordinator.data.get(self._idx) if coordinator.data else None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if str(self._idx) in self.coordinator.data:
            self._data = self.coordinator.data[str(self._idx)]
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.available:
            return False
        if not self._data:
            return False
        if str(self._idx) not in self.coordinator.data:
            return False
        # Check if device is online (received online: "1" from /will/ topic)
        # Note: Device may show data even when offline if we have cached data
        # We'll show available if we have data, but the device might be asleep
        return True

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Use group name, fall back to device name, then device type
        name = "Unknown"
        model = "Unknown"
        connections: set[tuple[str, str]] = set()
        if self._data:
            if self._data.name:
                name = self._data.name
            elif self._data.device and self._data.device.device_name:
                name = self._data.device.device_name
            elif self._data.device and self._data.device.device_type:
                name = self._data.device.device_type
            if self._data.device:
                model = self._data.device.device_type
                # Add Bluetooth MAC connection if available
                if self._data.device.ble_name:
                    connections.add(
                        (CONNECTION_BLUETOOTH, format_mac(self._data.device.ble_name))
                    )
        info_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, str(self._idx))},
            "name": name,
            "manufacturer": MANUFACTURER,
            "model": model,
            "connections": connections or None,
        }
        # HA's DeviceInfo TypedDict types connections as non-optional, but this
        # integration stores None to mean "unset"; cast the loosely-typed kwargs.
        return cast(DeviceInfo, info_kwargs)

    @property
    @override
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self._idx}"

    @property
    @override
    def activity(self) -> VacuumActivity | None:
        """Return the state of the device."""
        if not self._data:
            return None
        battery = self._data.get_dp(Battery)
        cleaning_status = self._data.get_dp(CleaningStatus)
        dock_status = self._data.get_dp(Dock)
        dock_connection = self._data.get_dp(DockConnectionStatus)

        # Check if returning to dock via CleaningStatus (DP 0) - primary indicator
        if cleaning_status is not None and cleaning_status.status in (
            CleaningStatusMode.RETURNING_TO_DOCK,
            CleaningStatusMode.RETURNING,
        ):
            return VacuumActivity.RETURNING

        # Check if returning via Dock DP (fallback for legacy behavior)
        if dock_status is not None and dock_status.status is DockStatus.RETURNING:
            return VacuumActivity.RETURNING

        # Check if docked - use dock status, dock connection status, or battery charging state
        is_docked = False
        if dock_status is not None and dock_status.status is DockStatus.DOCKED:
            is_docked = True
        elif dock_connection is not None:
            is_docked = dock_connection.is_docked
        elif battery is not None:
            is_docked = battery.charge_state in (
                BatteryState.CHARGING,
                BatteryState.CHARGED,
            )

        if is_docked:
            return VacuumActivity.DOCKED

        # Check cleaning status
        if cleaning_status is not None:
            if cleaning_status.status in (
                CleaningStatusMode.CLEANING,
                CleaningStatusMode.STARTING,
            ):
                return VacuumActivity.CLEANING
            if cleaning_status.status is CleaningStatusMode.STOPPED:
                return VacuumActivity.IDLE

        return None

    @property
    @override
    def fan_speed_list(self) -> list[str]:
        """Flag vacuum cleaner robot features that are supported."""
        return CleaningMode.CLEANING_MODES

    @property
    @override
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        if not self._data:
            return None
        fan_speed = self._data.get_dp(CleaningMode)
        if fan_speed is not None:
            return fan_speed.cleaning_mode
        return None

    @property
    @override
    def supported_features(self) -> VacuumEntityFeature:
        """Flag vacuum cleaner robot features that are supported."""
        return (
            VacuumEntityFeature.FAN_SPEED
            | VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.START
            | VacuumEntityFeature.STOP
        )

    async def _async_send_command(self, dp: GenericDP) -> None:
        """Send a command to the device, raising on failure."""
        if not self._data:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="device_unavailable"
            )
        if not await self.coordinator.async_send_command(self._data, dp):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_send_command"
            )

    @override
    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the fan speed of the vacuum cleaner."""
        try:
            mode = CleaningMode(mode=fan_speed)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_fan_speed",
                translation_placeholders={"fan_speed": fan_speed},
            ) from err
        await self._async_send_command(mode)

    @override
    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self._async_send_command(
            CleaningStatus(status=CleaningStatusMode.STOPPED)
        )

    @override
    async def async_start(self) -> None:
        """Start the vacuum cleaner."""
        await self._async_send_command(
            CleaningStatus(status=CleaningStatusMode.CLEANING)
        )

    @override
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return the vacuum cleaner to the dock."""
        await self._async_send_command(Dock(status=DockStatus.RETURNING))
