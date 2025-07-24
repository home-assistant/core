"""Support for LG webOS TV notification service."""

from __future__ import annotations

from typing import Any

from aiowebostv import WebOsClient

from homeassistant.components.notify import ATTR_DATA, BaseNotificationService
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import WebOsTvConfigEntry
from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN, WEBOSTV_EXCEPTIONS

PARALLEL_UPDATES = 0


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService | None:
    """Return the notify service."""

    if discovery_info is None:
        return None

    config_entry = hass.config_entries.async_get_entry(
        discovery_info[ATTR_CONFIG_ENTRY_ID]
    )
    assert config_entry is not None

    return LgWebOSNotificationService(config_entry)


class LgWebOSNotificationService(BaseNotificationService):
    """Implement the notification service for LG webOS TV."""

    def __init__(self, entry: WebOsTvConfigEntry) -> None:
        """Initialize the service."""
        self._entry = entry

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to the tv."""
        client: WebOsClient = self._entry.runtime_data
        data = kwargs[ATTR_DATA]
        icon_path = data.get(ATTR_ICON) if data else None

        if not client.tv_state.is_on:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="notify_device_off",
                translation_placeholders={
                    "name": str(self._entry.title),
                    "func": __name__,
                },
            )
        try:
            await client.send_message(message, icon_path=icon_path)
        except FileNotFoundError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="notify_icon_not_found",
                translation_placeholders={
                    "name": str(self._entry.title),
                    "icon_path": str(icon_path),
                },
            ) from error
        except WEBOSTV_EXCEPTIONS as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="notify_communication_error",
                translation_placeholders={
                    "name": str(self._entry.title),
                    "error": str(error),
                },
            ) from error
