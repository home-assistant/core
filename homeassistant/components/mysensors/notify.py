"""MySensors notification service."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .. import mysensors
from .const import DOMAIN, DevId, DiscoveryInfo


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService | None:
    """Get the MySensors notification service."""
    if not discovery_info:
        return None

    new_devices = mysensors.setup_mysensors_platform(
        hass,
        Platform.NOTIFY,
        cast(DiscoveryInfo, discovery_info),
        MySensorsNotificationDevice,
    )
    if not new_devices:
        return None
    return MySensorsNotificationService(hass)


class MySensorsNotificationDevice(mysensors.device.MySensorsDevice):
    """Represent a MySensors Notification device."""

    @callback
    def _async_update_callback(self) -> None:
        """Update the device."""
        self._async_update()

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
            hass, Platform.NOTIFY
        )  # type: ignore[assignment]
        self.hass = hass

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""
        target_devices = kwargs.get(ATTR_TARGET)
        devices = [
            device
            for device in self.devices.values()
            if target_devices is None or device.name in target_devices
        ]

        placeholders = {
            "alternate_service": "text.set_value",
            "deprecated_service": f"notify.{self._service_name}",
            "alternate_target": str(
                [f"text.{slugify(device.name)}" for device in devices]
            ),
        }

        async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_notify_service",
            breaks_in_ha_version="2023.4.0",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_service",
            translation_placeholders=placeholders,
        )

        for device in devices:
            device.send_msg(message)
