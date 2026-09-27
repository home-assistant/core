"""Describe KNX telegrams that update entity states."""

from collections.abc import Callable

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN, EVENT_KNX_TELEGRAM_RECEIVED


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe the sender of a KNX telegram."""

    @callback
    def async_describe_telegram(event: Event) -> dict[str, str]:
        """Describe the source recorded when the telegram was received."""
        source = event.data["source"]
        name = (
            f"{event.data['source_name']} ({source})"
            if event.data["source_name"]
            else source
        )
        return {
            LOGBOOK_ENTRY_NAME: name,
            LOGBOOK_ENTRY_MESSAGE: (
                f"sent a {event.data['telegramtype']} telegram"
                f" to {event.data['destination']}"
            ),
        }

    async_describe_event(DOMAIN, EVENT_KNX_TELEGRAM_RECEIVED, async_describe_telegram)
