"""Support for the Withings API.

For more details about this platform, please refer to the documentation at
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from aiohttp.hdrs import METH_POST
from aiohttp.web import Request, Response
from aiowithings import NotificationCategory, WithingsClient
from aiowithings.util import to_enum
import voluptuous as vol
from yarl import URL

from homeassistant.components import cloud
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import (
    async_generate_id as webhook_generate_id,
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PROFILES, CONF_USE_WEBHOOK, DEFAULT_TITLE, DOMAIN, LOGGER
from .coordinator import (
    WithingsActivityDataUpdateCoordinator,
    WithingsBedPresenceDataUpdateCoordinator,
    WithingsDataUpdateCoordinator,
    WithingsGoalsDataUpdateCoordinator,
    WithingsMeasurementDataUpdateCoordinator,
    WithingsSleepDataUpdateCoordinator,
    WithingsWorkoutDataUpdateCoordinator,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_PROFILES),
            cv.deprecated(CONF_CLIENT_ID),
            cv.deprecated(CONF_CLIENT_SECRET),
            vol.Schema(
                {
                    vol.Optional(CONF_CLIENT_ID): vol.All(cv.string, vol.Length(min=1)),
                    vol.Optional(CONF_CLIENT_SECRET): vol.All(
                        cv.string, vol.Length(min=1)
                    ),
                    vol.Optional(CONF_USE_WEBHOOK): cv.boolean,
                    vol.Optional(CONF_PROFILES): vol.All(
                        cv.ensure_list,
                        vol.Unique(),
                        vol.Length(min=1),
                        [vol.All(cv.string, vol.Length(min=1))],
                    ),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)
SUBSCRIBE_DELAY = timedelta(seconds=5)
UNSUBSCRIBE_DELAY = timedelta(seconds=1)
CONF_CLOUDHOOK_URL = "cloudhook_url"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Withings component."""

    if conf := config.get(DOMAIN):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Withings",
            },
        )
        if CONF_CLIENT_ID in conf:
            await async_import_client_credential(
                hass,
                DOMAIN,
                ClientCredential(
                    conf[CONF_CLIENT_ID],
                    conf[CONF_CLIENT_SECRET],
                ),
            )

    return True


@dataclass(slots=True)
class WithingsData:
    """Dataclass to hold withings domain data."""

    client: WithingsClient
    measurement_coordinator: WithingsMeasurementDataUpdateCoordinator
    sleep_coordinator: WithingsSleepDataUpdateCoordinator
    bed_presence_coordinator: WithingsBedPresenceDataUpdateCoordinator
    goals_coordinator: WithingsGoalsDataUpdateCoordinator
    activity_coordinator: WithingsActivityDataUpdateCoordinator
    workout_coordinator: WithingsWorkoutDataUpdateCoordinator
    coordinators: set[WithingsDataUpdateCoordinator] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Collect all coordinators in a set."""
        self.coordinators = {
            self.measurement_coordinator,
            self.sleep_coordinator,
            self.bed_presence_coordinator,
            self.goals_coordinator,
            self.activity_coordinator,
            self.workout_coordinator,
        }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Withings from a config entry."""
    if CONF_WEBHOOK_ID not in entry.data or entry.unique_id is None:
        new_data = entry.data.copy()
        unique_id = str(entry.data[CONF_TOKEN]["userid"])
        if CONF_WEBHOOK_ID not in new_data:
            new_data[CONF_WEBHOOK_ID] = webhook_generate_id()

        hass.config_entries.async_update_entry(
            entry, data=new_data, unique_id=unique_id
        )
    session = async_get_clientsession(hass)
    client = WithingsClient(session=session)
    implementation = await async_get_config_entry_implementation(hass, entry)
    oauth_session = OAuth2Session(hass, entry, implementation)

    refresh_lock = asyncio.Lock()

    async def _refresh_token() -> str:
        async with refresh_lock:
            await oauth_session.async_ensure_token_valid()
            token = oauth_session.token[CONF_ACCESS_TOKEN]
            if TYPE_CHECKING:
                assert isinstance(token, str)
            return token

    client.refresh_token_function = _refresh_token
    withings_data = WithingsData(
        client=client,
        measurement_coordinator=WithingsMeasurementDataUpdateCoordinator(hass, client),
        sleep_coordinator=WithingsSleepDataUpdateCoordinator(hass, client),
        bed_presence_coordinator=WithingsBedPresenceDataUpdateCoordinator(hass, client),
        goals_coordinator=WithingsGoalsDataUpdateCoordinator(hass, client),
        activity_coordinator=WithingsActivityDataUpdateCoordinator(hass, client),
        workout_coordinator=WithingsWorkoutDataUpdateCoordinator(hass, client),
    )

    for coordinator in withings_data.coordinators:
        await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = withings_data

    async def unregister_webhook(
        _: Any,
    ) -> None:
        LOGGER.debug("Unregister Withings webhook (%s)", entry.data[CONF_WEBHOOK_ID])
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
        await async_unsubscribe_webhooks(client)
        for coordinator in withings_data.coordinators:
            coordinator.webhook_subscription_listener(False)

    async def register_webhook(
        _: Any,
    ) -> None:
        if cloud.async_active_subscription(hass):
            webhook_url = await _async_cloudhook_generate_url(hass, entry)
        else:
            webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])
        url = URL(webhook_url)
        if url.scheme != "https" or url.port != 443:
            LOGGER.warning(
                "Webhook not registered - "
                "https and port 443 is required to register the webhook"
            )
            return

        webhook_name = "Withings"
        if entry.title != DEFAULT_TITLE:
            webhook_name = f"{DEFAULT_TITLE} {entry.title}"

        webhook_register(
            hass,
            DOMAIN,
            webhook_name,
            entry.data[CONF_WEBHOOK_ID],
            get_webhook_handler(withings_data),
            allowed_methods=[METH_POST],
        )

        await async_subscribe_webhooks(client, webhook_url)
        for coordinator in withings_data.coordinators:
            coordinator.webhook_subscription_listener(True)
        LOGGER.debug("Register Withings webhook: %s", webhook_url)
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
        )

    async def manage_cloudhook(state: cloud.CloudConnectionState) -> None:
        if state is cloud.CloudConnectionState.CLOUD_CONNECTED:
            await register_webhook(None)

        if state is cloud.CloudConnectionState.CLOUD_DISCONNECTED:
            await unregister_webhook(None)
            entry.async_on_unload(async_call_later(hass, 30, register_webhook))

    if cloud.async_active_subscription(hass):
        if cloud.async_is_connected(hass):
            entry.async_on_unload(async_call_later(hass, 1, register_webhook))
        entry.async_on_unload(
            cloud.async_listen_connection_change(hass, manage_cloudhook)
        )
    else:
        entry.async_on_unload(async_call_later(hass, 1, register_webhook))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Withings config entry."""
    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_subscribe_webhooks(client: WithingsClient, webhook_url: str) -> None:
    """Subscribe to Withings webhooks."""
    await async_unsubscribe_webhooks(client)

    notification_to_subscribe = {
        NotificationCategory.WEIGHT,
        NotificationCategory.PRESSURE,
        NotificationCategory.ACTIVITY,
        NotificationCategory.SLEEP,
        NotificationCategory.IN_BED,
        NotificationCategory.OUT_BED,
    }

    for notification in notification_to_subscribe:
        LOGGER.debug(
            "Subscribing %s for %s in %s seconds",
            webhook_url,
            notification,
            SUBSCRIBE_DELAY.total_seconds(),
        )
        # Withings will HTTP HEAD the callback_url and needs some downtime
        # between each call or there is a higher chance of failure.
        await asyncio.sleep(SUBSCRIBE_DELAY.total_seconds())
        await client.subscribe_notification(webhook_url, notification)


async def async_unsubscribe_webhooks(client: WithingsClient) -> None:
    """Unsubscribe to all Withings webhooks."""
    current_webhooks = await client.list_notification_configurations()

    for webhook_configuration in current_webhooks:
        LOGGER.debug(
            "Unsubscribing %s for %s in %s seconds",
            webhook_configuration.callback_url,
            webhook_configuration.notification_category,
            UNSUBSCRIBE_DELAY.total_seconds(),
        )
        # Quick calls to Withings can result in the service returning errors.
        # Give them some time to cool down.
        await asyncio.sleep(UNSUBSCRIBE_DELAY.total_seconds())
        await client.revoke_notification_configurations(
            webhook_configuration.callback_url,
            webhook_configuration.notification_category,
        )


async def _async_cloudhook_generate_url(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Generate the full URL for a webhook_id."""
    if CONF_CLOUDHOOK_URL not in entry.data:
        webhook_id = entry.data[CONF_WEBHOOK_ID]
        # Some users already have their webhook as cloudhook.
        # We remove them to be sure we can create a new one.
        with contextlib.suppress(ValueError):
            await cloud.async_delete_cloudhook(hass, webhook_id)
        webhook_url = await cloud.async_create_cloudhook(hass, webhook_id)
        data = {**entry.data, CONF_CLOUDHOOK_URL: webhook_url}
        hass.config_entries.async_update_entry(entry, data=data)
        return webhook_url
    return str(entry.data[CONF_CLOUDHOOK_URL])


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Cleanup when entry is removed."""
    if cloud.async_active_subscription(hass):
        try:
            LOGGER.debug(
                "Removing Withings cloudhook (%s)", entry.data[CONF_WEBHOOK_ID]
            )
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except cloud.CloudNotAvailable:
            pass


def json_message_response(message: str, message_code: int) -> Response:
    """Produce common json output."""
    return HomeAssistantView.json({"message": message, "code": message_code})


def get_webhook_handler(
    withings_data: WithingsData,
) -> Callable[[HomeAssistant, str, Request], Awaitable[Response | None]]:
    """Return webhook handler."""

    async def async_webhook_handler(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response | None:
        # Handle http post calls to the path.
        if not request.body_exists:
            return json_message_response("No request body", message_code=12)

        params = await request.post()

        if "appli" not in params:
            return json_message_response(
                "Parameter appli not provided", message_code=20
            )

        notification_category = to_enum(
            NotificationCategory,
            int(params.getone("appli")),  # type: ignore[arg-type]
            NotificationCategory.UNKNOWN,
        )

        for coordinator in withings_data.coordinators:
            if notification_category in coordinator.notification_categories:
                await coordinator.async_webhook_data_updated(notification_category)

        return json_message_response("Success", message_code=0)

    return async_webhook_handler
