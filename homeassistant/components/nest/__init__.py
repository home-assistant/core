"""Support for Nest devices."""

import asyncio
import logging

from google_nest_sdm.event import AsyncEventCallback, EventMessage
from google_nest_sdm.exceptions import AuthException, GoogleNestException
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    CONF_STRUCTURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import api, config_flow
from .const import (
    API_URL,
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    DATA_NEST_CONFIG,
    DATA_SDM,
    DATA_SUBSCRIBER,
    DOMAIN,
    SIGNAL_NEST_UPDATE,
)
from .events import EVENT_NAME_MAP, NEST_EVENT
from .legacy import async_setup_legacy, async_setup_legacy_entry

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema(
    {vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(cv.ensure_list)}
)


# The preferred method for set up is with an empty configuration.yaml, though
# this is still present for backwards compatibility.
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                # Required to use the new API (optional for compatibility)
                vol.Optional(CONF_PROJECT_ID): cv.string,
                vol.Optional(CONF_SUBSCRIBER_ID): cv.string,
                # Config that only currently works on the old API
                vol.Optional(CONF_STRUCTURE): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(CONF_SENSORS): SENSOR_SCHEMA,
                vol.Optional(CONF_BINARY_SENSORS): SENSOR_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Platforms for SDM API
PLATFORMS = ["sensor", "camera", "climate"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Nest components with dispatch between old/new flows."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    if CONF_PROJECT_ID not in config[DOMAIN]:
        return await async_setup_legacy(hass, config)

    if CONF_SUBSCRIBER_ID not in config[DOMAIN]:
        _LOGGER.error("Configuration option '{CONF_SUBSCRIBER_ID}' required")
        return False

    # For setup of ConfigEntry below prior to full config flow support
    hass.data[DOMAIN][DATA_NEST_CONFIG] = config[DOMAIN]
    return True


class SignalUpdateCallback(AsyncEventCallback):
    """An EventCallback invoked when new events arrive from subscriber."""

    def __init__(self, hass: HomeAssistant):
        """Initialize EventCallback."""
        self._hass = hass

    async def async_handle_event(self, event_message: EventMessage):
        """Process an incoming EventMessage."""
        if not event_message.resource_update_name:
            _LOGGER.debug("Ignoring event with no device_id")
            return
        device_id = event_message.resource_update_name
        _LOGGER.debug("Update for %s @ %s", device_id, event_message.timestamp)
        traits = event_message.resource_update_traits
        if traits:
            _LOGGER.debug("Trait update %s", traits.keys())
            # This event triggered an update to a device that changed some
            # properties which the DeviceManager should already have received.
            # Send a signal to refresh state of all listening devices.
            async_dispatcher_send(self._hass, SIGNAL_NEST_UPDATE)
        events = event_message.resource_update_events
        if not events:
            return
        _LOGGER.debug("Event Update %s", events.keys())
        device_registry = await self._hass.helpers.device_registry.async_get_registry()
        device_entry = device_registry.async_get_device({(DOMAIN, device_id)}, ())
        if not device_entry:
            _LOGGER.debug("Ignoring event for unregistered device '%s'", device_id)
            return
        for event in events:
            event_type = EVENT_NAME_MAP.get(event)
            if not event_type:
                continue
            message = {
                "device_id": device_entry.id,
                "type": event_type,
            }
            self._hass.bus.async_fire(NEST_EVENT, message)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Nest from a config entry with dispatch between old/new flows."""

    if DATA_SDM not in entry.data:
        return await async_setup_legacy_entry(hass, entry)

    if CONF_PROJECT_ID in entry.data:
        config = entry.data
    else:
        config = hass.data[DOMAIN][DATA_NEST_CONFIG]

    implementation = config_flow.NestFlowHandler.async_register_oauth(
        hass,
        config[CONF_CLIENT_ID],
        config[CONF_CLIENT_SECRET],
        config[CONF_PROJECT_ID],
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass),
        session,
        API_URL,
    )
    subscriber = GoogleNestSubscriber(
        auth, config[CONF_PROJECT_ID], config[CONF_SUBSCRIBER_ID]
    )
    subscriber.set_update_callback(SignalUpdateCallback(hass))

    try:
        await subscriber.start_async()
    except AuthException as err:
        _LOGGER.debug("Subscriber authentication error: %s", err)
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_REAUTH},
                data=entry.data,
            )
        )
        return False
    except GoogleNestException as err:
        _LOGGER.error("Subscriber error: %s", err)
        subscriber.stop_async()
        raise ConfigEntryNotReady from err

    try:
        await subscriber.async_get_device_manager()
    except GoogleNestException as err:
        _LOGGER.error("Device Manager error: %s", err)
        subscriber.stop_async()
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][DATA_SUBSCRIBER] = subscriber

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if DATA_SDM not in entry.data:
        # Legacy API
        return True

    subscriber = hass.data[DOMAIN][DATA_SUBSCRIBER]
    subscriber.stop_async()
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(DATA_SUBSCRIBER)

    return unload_ok
