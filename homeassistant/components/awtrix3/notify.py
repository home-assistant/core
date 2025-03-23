"""Support for Awtrix notifications."""

import logging

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .common import (
    async_get_coordinator_by_device_name,
    async_get_coordinator_devices,
    getIcon,
)
from .coordinator import AwtrixCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService:
    """Get the AWTRIX notification service."""

    if discovery_info is None:
        return None

    return AwtrixNotificationService(hass=hass,
                                     coordinator=discovery_info.get("coordinator", None))


########################################################################################################

class AwtrixNotificationService(BaseNotificationService):
    """Implement the notification service for Awtrix."""

    def __init__(self, hass: HomeAssistant, coordinator: AwtrixCoordinator) -> None:
        """Init the notification service for Awtrix."""

        self.hass = hass
        self.coordinator = coordinator

    async def async_send_message(self, message='', **kwargs):
        """Send a message to some Awtrix device."""

        apis = []
        if self.coordinator is None:
            target_ids = kwargs.get(ATTR_TARGET, 'all')
            if target_ids == 'all':
                coordinators = async_get_coordinator_devices(self.hass)
                apis = [x.api for x in coordinators]
            else:
                coordinators = async_get_coordinator_by_device_name(self.hass, target_ids)
                apis = [x.api for x in coordinators]
        else:
            apis.append(self.coordinator.api)

        data = kwargs.get(ATTR_DATA)
        for api in apis:
            await self.notification(api, message, data)

        return True

    async def notification(self, api, message, data):
        """Handle the notification service for Awtrix."""

        data = data or {}
        msg = data.copy()
        msg["text"] = message

        if 'icon' in msg:
            if str(msg["icon"]).startswith(('http://', 'https://')):
                icon = await self.hass.async_add_executor_job(getIcon, str(msg["icon"]))
                if icon:
                    msg["icon"] = icon

        command = "notify/dismiss" if not message else "notify"
        return await api.device_set_item_value(command, msg)
