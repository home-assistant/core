"""MySensors notification service."""
from __future__ import annotations

from typing import Any

from homeassistant.components import mysensors
from homeassistant.components.notify import ATTR_TARGET, DOMAIN, BaseNotificationService
from homeassistant.core import HomeAssistant

from .const import DevId, DiscoveryInfo


async def async_get_service(
    hass: HomeAssistant,
    config: dict[str, Any],
    discovery_info: DiscoveryInfo | None = None,
) -> BaseNotificationService | None:
    """Get the MySensors notification service."""
    if not discovery_info:
        return None

    new_devices = mysensors.setup_mysensors_platform(
        hass, DOMAIN, discovery_info, MySensorsNotificationDevice
    )
    if not new_devices:
        return None
    return MySensorsNotificationService(hass)


class MySensorsNotificationDevice(mysensors.device.MySensorsDevice):
    """Represent a MySensors Notification device."""

    def send_msg(self, msg: str) -> None:
        """Send a message."""
        for sub_msg in [msg[i : i + 25] for i in range(0, len(msg), 25)]:
            # Max mysensors payload is 25 bytes.
            self.gateway.set_child_value(
                self.node_id, self.child_id, self.value_type, sub_msg
            )

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<MySensorsNotificationDevice {self.name}>"


class MySensorsNotificationService(BaseNotificationService):
    """Implement a MySensors notification service."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service."""
        self.devices: dict[
            DevId, MySensorsNotificationDevice
        ] = mysensors.get_mysensors_devices(
            hass, DOMAIN
        )  # type: ignore[assignment]

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""
        target_devices = kwargs.get(ATTR_TARGET)
        devices = [
            device
            for device in self.devices.values()
            if target_devices is None or device.name in target_devices
        ]

        for device in devices:
            device.send_msg(message)
