"""Send instance and usage analytics."""

from typing import Any

import voluptuous as vol

from homeassistant.components import labs, websocket_api
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .analytics import (
    Analytics,
    AnalyticsInput,
    AnalyticsModifications,
    DeviceAnalyticsModifications,
    EntityAnalyticsModifications,
    async_devices_payload,
)
from .const import (
    ATTR_ONBOARDED,
    ATTR_PREFERENCES,
    ATTR_SNAPSHOTS,
    DOMAIN,
    PREFERENCE_SCHEMA,
)
from .http import AnalyticsDevicesView

__all__ = [
    "AnalyticsInput",
    "AnalyticsModifications",
    "DeviceAnalyticsModifications",
    "EntityAnalyticsModifications",
    "async_devices_payload",
]

CONF_SNAPSHOTS_URL = "snapshots_url"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_SNAPSHOTS_URL): vol.Any(str, None),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

DATA_COMPONENT: HassKey[Analytics] = HassKey(DOMAIN)

LABS_SNAPSHOT_FEATURE = "snapshots"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the analytics integration."""
    analytics_config = config.get(DOMAIN, {})

    if CONF_SNAPSHOTS_URL in analytics_config:
        await labs.async_update_preview_feature(
            hass, DOMAIN, LABS_SNAPSHOT_FEATURE, enabled=True
        )
        snapshots_url = analytics_config[CONF_SNAPSHOTS_URL]
    else:
        snapshots_url = None

    analytics = Analytics(hass, snapshots_url)

    # Load stored data
    await analytics.load()

    started = False

    async def _async_handle_labs_update(
        event: Event[labs.EventLabsUpdatedData],
    ) -> None:
        """Handle labs feature toggle."""
        await analytics.save_preferences({ATTR_SNAPSHOTS: event.data["enabled"]})
        if started:
            await analytics.async_schedule()

    @callback
    def _async_labs_event_filter(event_data: labs.EventLabsUpdatedData) -> bool:
        """Filter labs events for this integration's snapshot feature."""
        return (
            event_data["domain"] == DOMAIN
            and event_data["preview_feature"] == LABS_SNAPSHOT_FEATURE
        )

    async def start_schedule(_event: Event) -> None:
        """Start the send schedule after the started event."""
        nonlocal started
        started = True
        await analytics.async_schedule()

    hass.bus.async_listen(
        labs.EVENT_LABS_UPDATED,
        _async_handle_labs_update,
        event_filter=_async_labs_event_filter,
    )
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_schedule)

    websocket_api.async_register_command(hass, websocket_analytics)
    websocket_api.async_register_command(hass, websocket_analytics_preferences)

    hass.http.register_view(AnalyticsDevicesView)

    hass.data[DATA_COMPONENT] = analytics
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
    analytics = hass.data[DATA_COMPONENT]
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
    analytics = hass.data[DATA_COMPONENT]

    await analytics.save_preferences(preferences)
    await analytics.async_schedule()

    connection.send_result(
        msg["id"],
        {ATTR_PREFERENCES: analytics.preferences},
    )
