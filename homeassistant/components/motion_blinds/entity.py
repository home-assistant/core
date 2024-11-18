"""Support for Motionblinds using their WLAN API."""

from __future__ import annotations

from motionblinds import DEVICE_TYPES_GATEWAY, DEVICE_TYPES_WIFI, MotionGateway
from motionblinds.motion_blinds import MotionBlind

from homeassistant.core import CALLBACK_TYPE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_AVAILABLE,
    DEFAULT_GATEWAY_NAME,
    DOMAIN,
    KEY_GATEWAY,
    MANUFACTURER,
    UPDATE_INTERVAL_MOVING,
    UPDATE_INTERVAL_MOVING_WIFI,
)
from .coordinator import DataUpdateCoordinatorMotionBlinds
from .gateway import device_name


class MotionCoordinatorEntity(CoordinatorEntity[DataUpdateCoordinatorMotionBlinds]):
    """Representation of a Motionblind entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinatorMotionBlinds,
        blind: MotionGateway | MotionBlind,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._blind = blind
        self._api_lock = coordinator.api_lock

        self._requesting_position: CALLBACK_TYPE | None = None
        self._previous_positions: list[int | dict | None] = []

        if blind.device_type in DEVICE_TYPES_WIFI:
            self._update_interval_moving = UPDATE_INTERVAL_MOVING_WIFI
        else:
            self._update_interval_moving = UPDATE_INTERVAL_MOVING

        if blind.device_type in DEVICE_TYPES_GATEWAY:
            gateway = blind
        else:
            gateway = blind._gateway  # noqa: SLF001
        if gateway.firmware is not None:
            sw_version = f"{gateway.firmware}, protocol: {gateway.protocol}"
        else:
            sw_version = f"Protocol: {gateway.protocol}"

        if blind.device_type in DEVICE_TYPES_GATEWAY:
            self._attr_device_info = DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, blind.mac)},
                identifiers={(DOMAIN, blind.mac)},
                manufacturer=MANUFACTURER,
                name=DEFAULT_GATEWAY_NAME,
                model="Wi-Fi bridge",
                sw_version=sw_version,
            )
        elif blind.device_type in DEVICE_TYPES_WIFI:
            self._attr_device_info = DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, blind.mac)},
                identifiers={(DOMAIN, blind.mac)},
                manufacturer=MANUFACTURER,
                model=blind.blind_type,
                name=device_name(blind),
                sw_version=sw_version,
                hw_version=blind.wireless_name,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, blind.mac)},
                manufacturer=MANUFACTURER,
                model=blind.blind_type,
                name=device_name(blind),
                via_device=(DOMAIN, blind._gateway.mac),  # noqa: SLF001
                hw_version=blind.wireless_name,
            )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.coordinator.data is None:
            return False

        gateway_available = self.coordinator.data[KEY_GATEWAY][ATTR_AVAILABLE]
        if not gateway_available or self._blind.device_type in DEVICE_TYPES_GATEWAY:
            return gateway_available

        return self.coordinator.data[self._blind.mac][ATTR_AVAILABLE]

    async def async_added_to_hass(self) -> None:
        """Subscribe to multicast pushes and register signal handler."""
        self._blind.Register_callback(self.unique_id, self.schedule_update_ha_state)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed."""
        self._blind.Remove_callback(self.unique_id)
        await super().async_will_remove_from_hass()

    async def async_scheduled_update_request(self, *_) -> None:
        """Request a state update from the blind at a scheduled point in time."""
        # add the last position to the list and keep the list at max 2 items
        self._previous_positions.append(self._blind.position)
        if len(self._previous_positions) > 2:
            del self._previous_positions[: len(self._previous_positions) - 2]

        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Update_trigger)

        self.coordinator.async_update_listeners()

        if len(self._previous_positions) < 2 or not all(
            self._blind.position == prev_position
            for prev_position in self._previous_positions
        ):
            # keep updating the position @self._update_interval_moving until the position does not change.
            self._requesting_position = async_call_later(
                self.hass,
                self._update_interval_moving,
                self.async_scheduled_update_request,
            )
        else:
            self._previous_positions = []
            self._requesting_position = None

    async def async_request_position_till_stop(self, delay: int | None = None) -> None:
        """Request the position of the blind every self._update_interval_moving seconds until it stops moving."""
        if delay is None:
            delay = self._update_interval_moving

        self._previous_positions = []
        if self._blind.position is None:
            return
        if self._requesting_position is not None:
            self._requesting_position()

        self._requesting_position = async_call_later(
            self.hass, delay, self.async_scheduled_update_request
        )
