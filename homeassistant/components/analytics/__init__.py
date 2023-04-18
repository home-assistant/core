"""Send instance and usage analytics."""
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HassJob, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .analytics import Analytics
from .const import ATTR_ONBOARDED, ATTR_PREFERENCES, DOMAIN, INTERVAL, PREFERENCE_SCHEMA


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up the analytics integration."""
    analytics = Analytics(hass)

    # Load stored data
    await analytics.load()

    @callback
    def start_schedule(_event: Event) -> None:
        """Start the send schedule after the started event."""
        # Wait 15 min after started
        async_call_later(
            hass,
            900,
            HassJob(
                analytics.send_analytics,
                name="analytics schedule",
                cancel_on_shutdown=True,
            ),
        )

        # Send every day
        async_track_time_interval(
            hass,
            analytics.send_analytics,
            INTERVAL,
            name="analytics daily",
            cancel_on_shutdown=True,
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_schedule)

    websocket_api.async_register_command(hass, websocket_analytics)
    websocket_api.async_register_command(hass, websocket_analytics_preferences)

    hass.data[DOMAIN] = analytics
    return True


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "analytics"})
def websocket_analytics(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return analytics preferences."""
    analytics: Analytics = hass.data[DOMAIN]
    connection.send_result(
        msg["id"],
        {ATTR_PREFERENCES: analytics.preferences, ATTR_ONBOARDED: analytics.onboarded},
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "analytics/preferences",
        vol.Required("preferences", default={}): PREFERENCE_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_analytics_preferences(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update analytics preferences."""
    preferences = msg[ATTR_PREFERENCES]
    analytics: Analytics = hass.data[DOMAIN]

    await analytics.save_preferences(preferences)
    await analytics.send_analytics()

    connection.send_result(
        msg["id"],
        {ATTR_PREFERENCES: analytics.preferences},
    )
