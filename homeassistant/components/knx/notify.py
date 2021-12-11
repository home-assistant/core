"""Support for KNX/IP notification services."""
from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import Notification as XknxNotification

from homeassistant.components.notify import BaseNotificationService
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, KNX_ADDRESS


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> KNXNotificationService | None:
    """Get the KNX notification service."""
    if not discovery_info:
        return None

    platform_config: dict = discovery_info
    xknx: XKNX = hass.data[DOMAIN].xknx

    notification_devices = []
    for device_config in platform_config:
        notification_devices.append(
            XknxNotification(
                xknx,
                name=device_config[CONF_NAME],
                group_address=device_config[KNX_ADDRESS],
            )
        )
    return (
        KNXNotificationService(notification_devices) if notification_devices else None
    )


class KNXNotificationService(BaseNotificationService):
    """Implement demo notification service."""

    def __init__(self, devices: list[XknxNotification]) -> None:
        """Initialize the service."""
        self.devices = devices

    @property
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        ret = {}
        for device in self.devices:
            ret[device.name] = device.name
        return ret

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a notification to knx bus."""
        if "target" in kwargs:
            await self._async_send_to_device(message, kwargs["target"])
        else:
            await self._async_send_to_all_devices(message)

    async def _async_send_to_all_devices(self, message: str) -> None:
        """Send a notification to knx bus to all connected devices."""
        for device in self.devices:
            await device.set(message)

    async def _async_send_to_device(self, message: str, names: str) -> None:
        """Send a notification to knx bus to device with given names."""
        for device in self.devices:
            if device.name in names:
                await device.set(message)
