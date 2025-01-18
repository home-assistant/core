"""Implementation of the lock platform."""

from igloohome_api import (
    BRIDGE_JOB_LOCK,
    BRIDGE_JOB_UNLOCK,
    DEVICE_TYPE_BRIDGE,
    DEVICE_TYPE_LOCK,
    Api as IgloohomeApi,
    GetDeviceInfoResponse,
)

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IgloohomeConfigEntry
from .entity import IgloohomeBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IgloohomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lock entities."""
    async_add_entities(
        (
            IgloohomeLockEntity(
                api_device_info=device,
                api=entry.runtime_data.api,
                bridgeId=str(
                    __get_linked_bridge(device.deviceId, entry.runtime_data.devices)
                ),
            )
            for device in entry.runtime_data.devices
            if device.type == DEVICE_TYPE_LOCK
            and __get_linked_bridge(device.deviceId, entry.runtime_data.devices)
            is not None
        ),
        update_before_add=True,
    )


class IgloohomeLockEntity(IgloohomeBaseEntity, LockEntity):
    """Implementation of a device that has locking capabilities."""

    # Operating on assumed state because there is no API to query the state.
    _attr_assumed_state = True

    def __init__(
        self, api_device_info: GetDeviceInfoResponse, api: IgloohomeApi, bridgeId: str
    ) -> None:
        """Initialize the class."""
        super().__init__(
            api_device_info=api_device_info,
            api=api,
            unique_key="lock",
        )
        self._attr_supported_features |= LockEntityFeature.OPEN
        self.bridgeId = bridgeId

    async def async_lock(self, **kwargs):
        """Lock this lock."""
        await self.api.create_bridge_proxied_job(
            self.api_device_info.deviceId, self.bridgeId, BRIDGE_JOB_LOCK
        )

    async def async_unlock(self, **kwargs):
        """Unlock this lock."""
        await self.api.create_bridge_proxied_job(
            self.api_device_info.deviceId, self.bridgeId, BRIDGE_JOB_UNLOCK
        )

    async def async_open(self, **kwargs):
        """Open (unlatch) this lock."""
        await self.api.create_bridge_proxied_job(
            self.api_device_info.deviceId, self.bridgeId, BRIDGE_JOB_UNLOCK
        )


def __get_linked_bridge(
    device_id: str, devices: list[GetDeviceInfoResponse]
) -> str | None:
    """Return the ID of the bridge that is linked to the device. None if no bridge is linked."""
    bridges = (bridge for bridge in devices if bridge.type == DEVICE_TYPE_BRIDGE)
    for bridge in bridges:
        if device_id in (
            linked_device.deviceId for linked_device in bridge.linkedDevices
        ):
            return bridge.deviceId
    return None
