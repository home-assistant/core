"""Support for Google Assistant SDK broadcast notifications."""
from __future__ import annotations

from typing import Any

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_LANGUAGE_CODE, DOMAIN
from .helpers import async_send_text_commands, default_language_code

# https://support.google.com/assistant/answer/9071582?hl=en
LANG_TO_BROADCAST_COMMAND = {
    "en": ("broadcast", "broadcast to"),
    "de": ("Nachricht an alle", "Nachricht an alle an"),
    "es": ("Anuncia", "Anuncia en"),
    "fr": ("Diffuse", "Diffuse dans"),
    "it": ("Trasmetti", "Trasmetti in"),
    "pt": ("Transmite", "Transmite para"),
}


def broadcast_commands(language_code: str):
    """
    Get the commands for broadcasting a message for the given language code.

    Return type is a tuple where [0] is for broadcasting to your entire home,
    while [1] is for broadcasting to a specific target.
    """
    return LANG_TO_BROADCAST_COMMAND.get(language_code.split("-", maxsplit=1)[0])


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService:
    """Get the broadcast notification service."""
    return BroadcastNotificationService(hass)


class BroadcastNotificationService(BaseNotificationService):
    """Implement broadcast notification service."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service."""
        self.hass = hass

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message."""
        if not message:
            return

        # There can only be 1 entry (config_flow has single_instance_allowed)
        entry: ConfigEntry = self.hass.config_entries.async_entries(DOMAIN)[0]
        language_code = entry.options.get(
            CONF_LANGUAGE_CODE, default_language_code(self.hass)
        )

        commands = []
        targets = kwargs.get(ATTR_TARGET)
        if not targets:
            commands.append(f"{broadcast_commands(language_code)[0]} {message}")
        else:
            for target in targets:
                commands.append(
                    f"{broadcast_commands(language_code)[1]} {target} {message}"
                )
        await async_send_text_commands(commands, self.hass)
