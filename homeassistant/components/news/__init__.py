"""The news integration."""
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.frame import get_integration_frame

from .const import (
    ATTR_EVENTS,
    ATTR_SOURCES,
    DISPATCHER_NEWS_EVENT,
    DOMAIN,
    SOURCE_UPDATE_INTERVAL,
    SOURCES_SCHEMA,
)
from .manager import NewsManager


async def register_news_event(
    hass: HomeAssistant, event_id: str, event_data: dict
) -> None:
    """Register a news event from other integrations."""
    _, integration, path = get_integration_frame({DOMAIN})
    if path == "custom_components/":
        # We don't allow custom integrations to register news events
        return

    manager: NewsManager = hass.data[DOMAIN]
    await manager.register_event(f"integration.{integration}", event_id, event_data)


async def async_setup(hass: HomeAssistant, _) -> bool:
    """Set up the News integration."""
    manager = NewsManager(hass)
    await manager.load()
    hass.data[DOMAIN] = manager

    async def start_schedule(_event):
        """Start the send schedule after the started event."""
        await manager.update_sources()

        # Schedule source update interval
        async_track_time_interval(hass, manager.update_sources, SOURCE_UPDATE_INTERVAL)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_schedule)

    websocket_api.async_register_command(hass, websocket_news)
    websocket_api.async_register_command(hass, websocket_news_dismiss_event)
    websocket_api.async_register_command(hass, websocket_news_sources)
    websocket_api.async_register_command(hass, websocket_subscribe)

    return True


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "news"})
def websocket_news(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Return sources and active events."""
    manager: NewsManager = hass.data[DOMAIN]
    connection.send_result(
        msg["id"], {ATTR_SOURCES: manager.sources, ATTR_EVENTS: manager.events}
    )


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "news/dismiss_event",
        vol.Required("event_key"): str,
    }
)
async def websocket_news_dismiss_event(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Dismiss an event."""
    manager: NewsManager = hass.data[DOMAIN]
    await manager.dismiss_event(msg["event_key"])
    connection.send_result(msg["id"], manager.events)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "news/sources",
        vol.Required("sources"): SOURCES_SCHEMA,
    }
)
async def websocket_news_sources(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Update sources."""
    manager: NewsManager = hass.data[DOMAIN]
    await manager.manage_sources(msg[ATTR_SOURCES])

    connection.send_result(
        msg["id"],
        manager.sources,
    )


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "news/subscribe"})
async def websocket_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Subscribe to news events."""

    @callback
    def forward_messages(data):
        """Forward events to websocket connection."""
        connection.send_message(websocket_api.event_message(msg["id"], data))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, DISPATCHER_NEWS_EVENT, forward_messages
    )
    connection.send_message(websocket_api.result_message(msg["id"]))
