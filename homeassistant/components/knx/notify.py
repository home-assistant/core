"""Support for KNX/IP notifications."""

from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import Notification as XknxNotification

from homeassistant import config_entries
from homeassistant.components.notify import (
    BaseNotificationService,
    NotifyEntity,
    migrate_notify_issue,
)
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_KNX_CONFIG, DOMAIN, KNX_ADDRESS
from .knx_entity import KnxEntity


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> KNXNotificationService | None:
    """Get the KNX notification service."""
    if discovery_info is None:
        return None

    if platform_config := hass.data[DATA_KNX_CONFIG].get(Platform.NOTIFY):
        xknx: XKNX = hass.data[DOMAIN].xknx

        notification_devices = [
            _create_notification_instance(xknx, device_config)
            for device_config in platform_config
        ]
        return KNXNotificationService(notification_devices)

    return None


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
        migrate_notify_issue(self.hass, DOMAIN, "KNX", "2024.11.0")
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up notify(s) for KNX platform."""
    xknx: XKNX = hass.data[DOMAIN].xknx
    config: list[ConfigType] = hass.data[DATA_KNX_CONFIG][Platform.NOTIFY]

    async_add_entities(KNXNotify(xknx, entity_config) for entity_config in config)


def _create_notification_instance(xknx: XKNX, config: ConfigType) -> XknxNotification:
    """Return a KNX Notification to be used within XKNX."""
    return XknxNotification(
        xknx,
        name=config[CONF_NAME],
        group_address=config[KNX_ADDRESS],
        value_type=config[CONF_TYPE],
    )


class KNXNotify(KnxEntity, NotifyEntity):
    """Representation of a KNX notification entity."""

    _device: XknxNotification

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize a KNX notification."""
        super().__init__(_create_notification_instance(xknx, config))
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.remote_value.group_address)

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a notification to knx bus."""
        await self._device.set(message)
