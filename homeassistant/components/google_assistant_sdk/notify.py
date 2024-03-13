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
    "en": ("broadcast {0}", "broadcast to {1} {0}"),
    "de": ("Nachricht an alle {0}", "Nachricht an alle an {1} {0}"),
    "es": ("Anuncia {0}", "Anuncia en {1} {0}"),
    "fr": ("Diffuse {0}", "Diffuse dans {1} {0}"),
    "it": ("Trasmetti {0}", "Trasmetti in {1} {0}"),
    "ja": ("{0}とブロードキャストして", "{0}と{1}にブロードキャストして"),
    "ko": ("{0} 라고 방송해 줘", "{0} 라고 {1}에 방송해 줘"),
    "pt": ("Transmitir {0}", "Transmitir {0} para {1}"),
}


def broadcast_commands(language_code: str) -> tuple[str, str]:
    """Get the commands for broadcasting a message for the given language code.

    Return type is a tuple where [0] is for broadcasting to your entire home,
    while [1] is for broadcasting to a specific target.
    """
    return LANG_TO_BROADCAST_COMMAND[language_code.split("-", maxsplit=1)[0]]


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

        commands: list[str] = []
        targets = kwargs.get(ATTR_TARGET)
        if not targets:
            commands.append(broadcast_commands(language_code)[0].format(message))
        else:
            for target in targets:
                commands.append(
                    broadcast_commands(language_code)[1].format(message, target)
                )
        await async_send_text_commands(self.hass, commands)
