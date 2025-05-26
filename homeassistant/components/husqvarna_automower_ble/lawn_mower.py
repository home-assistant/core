"""The Husqvarna Autoconnect Bluetooth lawn mower platform."""

from __future__ import annotations

from automower_ble.protocol import MowerActivity, MowerState

from homeassistant.components import bluetooth
from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .coordinator import HusqvarnaCoordinator
from .entity import HusqvarnaAutomowerBleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AutomowerLawnMower integration from a config entry."""
    coordinator: HusqvarnaCoordinator = config_entry.runtime_data
    address = coordinator.address

    async_add_entities(
        [
            AutomowerLawnMower(
                coordinator,
                address,
            ),
        ]
    )


class AutomowerLawnMower(HusqvarnaAutomowerBleEntity, LawnMowerEntity):
    """Husqvarna Automower."""

    _attr_name = None
    _attr_supported_features = (
        LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(
        self,
        coordinator: HusqvarnaCoordinator,
        address: str,
    ) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator)
        self._attr_unique_id = str(address)

    def _get_activity(self) -> LawnMowerActivity | None:
        """Return the current lawn mower activity."""
        if self.coordinator.data is None:
            return None

        state = self.coordinator.data["state"]
        activity = self.coordinator.data["activity"]

        if state is None or activity is None:
            return None

        if state == MowerState.PAUSED:
            return LawnMowerActivity.PAUSED
        if state in (MowerState.STOPPED, MowerState.OFF, MowerState.WAIT_FOR_SAFETYPIN):
            # This is actually stopped, but that isn't an option
            return LawnMowerActivity.ERROR
        if state in (
            MowerState.RESTRICTED,
            MowerState.IN_OPERATION,
            MowerState.PENDING_START,
        ):
            if activity in (
                MowerActivity.CHARGING,
                MowerActivity.PARKED,
                MowerActivity.NONE,
            ):
                return LawnMowerActivity.DOCKED
            if activity in (MowerActivity.GOING_OUT, MowerActivity.MOWING):
                return LawnMowerActivity.MOWING
            if activity == MowerActivity.GOING_HOME:
                return LawnMowerActivity.RETURNING
        return LawnMowerActivity.ERROR

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("AutomowerLawnMower: _handle_coordinator_update")

        self._attr_activity = self._get_activity()
        self._attr_available = self._attr_activity is not None
        super()._handle_coordinator_update()

    async def async_start_mowing(self) -> None:
        """Start mowing."""
        LOGGER.debug("Starting mower")

        if not self.coordinator.mower.is_connected():
            device = bluetooth.async_ble_device_from_address(
                self.coordinator.hass, self.coordinator.address, connectable=True
            )
            if not await self.coordinator.mower.connect(device):
                return

        await self.coordinator.mower.mower_resume()
        if self._attr_activity is LawnMowerActivity.DOCKED:
            await self.coordinator.mower.mower_override()
        await self.coordinator.async_request_refresh()

        self._attr_activity = self._get_activity()
        self.async_write_ha_state()

    async def async_dock(self) -> None:
        """Start docking."""
        LOGGER.debug("Start docking")

        if not self.coordinator.mower.is_connected():
            device = bluetooth.async_ble_device_from_address(
                self.coordinator.hass, self.coordinator.address, connectable=True
            )
            if not await self.coordinator.mower.connect(device):
                return

        await self.coordinator.mower.mower_park()
        await self.coordinator.async_request_refresh()

        self._attr_activity = self._get_activity()
        self.async_write_ha_state()

    async def async_pause(self) -> None:
        """Pause mower."""
        LOGGER.debug("Pausing mower")

        if not self.coordinator.mower.is_connected():
            device = bluetooth.async_ble_device_from_address(
                self.coordinator.hass, self.coordinator.address, connectable=True
            )
            if not await self.coordinator.mower.connect(device):
                return

        await self.coordinator.mower.mower_pause()
        await self.coordinator.async_request_refresh()

        self._attr_activity = self._get_activity()
        self.async_write_ha_state()
