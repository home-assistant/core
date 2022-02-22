"""Support for Logi Circle devices."""
import asyncio

from aiohttp.client_exceptions import ClientResponseError
import async_timeout
from logi_circle import LogiCircle
from logi_circle.exception import AuthorizationFailed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.components.camera import ATTR_FILENAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    CONF_API_KEY,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from . import config_flow
from .const import (
    CONF_REDIRECT_URI,
    DATA_LOGI,
    DEFAULT_CACHEDB,
    DOMAIN,
    LED_MODE_KEY,
    RECORDING_MODE_KEY,
    SENSOR_TYPES,
    SIGNAL_LOGI_CIRCLE_RECONFIGURE,
    SIGNAL_LOGI_CIRCLE_RECORD,
    SIGNAL_LOGI_CIRCLE_SNAPSHOT,
)

NOTIFICATION_ID = "logi_circle_notification"
NOTIFICATION_TITLE = "Logi Circle Setup"

_TIMEOUT = 15  # seconds

SERVICE_SET_CONFIG = "set_config"
SERVICE_LIVESTREAM_SNAPSHOT = "livestream_snapshot"
SERVICE_LIVESTREAM_RECORD = "livestream_record"

ATTR_VALUE = "value"
ATTR_DURATION = "duration"

PLATFORMS = [Platform.CAMERA, Platform.SENSOR]

SENSOR_KEYS = [desc.key for desc in SENSOR_TYPES]

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        )
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_REDIRECT_URI): cv.string,
                vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

LOGI_CIRCLE_SERVICE_SET_CONFIG = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(ATTR_MODE): vol.In([LED_MODE_KEY, RECORDING_MODE_KEY]),
        vol.Required(ATTR_VALUE): cv.boolean,
    }
)

LOGI_CIRCLE_SERVICE_SNAPSHOT = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(ATTR_FILENAME): cv.template,
    }
)

LOGI_CIRCLE_SERVICE_RECORD = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(ATTR_FILENAME): cv.template,
        vol.Required(ATTR_DURATION): cv.positive_int,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up configured Logi Circle component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    config_flow.register_flow_implementation(
        hass,
        DOMAIN,
        client_id=conf[CONF_CLIENT_ID],
        client_secret=conf[CONF_CLIENT_SECRET],
        api_key=conf[CONF_API_KEY],
        redirect_uri=conf[CONF_REDIRECT_URI],
        sensors=conf[CONF_SENSORS],
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Logi Circle from a config entry."""
    logi_circle = LogiCircle(
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        api_key=entry.data[CONF_API_KEY],
        redirect_uri=entry.data[CONF_REDIRECT_URI],
        cache_file=hass.config.path(DEFAULT_CACHEDB),
    )

    if not logi_circle.authorized:
        persistent_notification.create(
            hass,
            (
                f"Error: The cached access tokens are missing from {DEFAULT_CACHEDB}.<br />"
                f"Please unload then re-add the Logi Circle integration to resolve."
            ),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    try:
        async with async_timeout.timeout(_TIMEOUT):
            # Ensure the cameras property returns the same Camera objects for
            # all devices. Performs implicit login and session validation.
            await logi_circle.synchronize_cameras()
    except AuthorizationFailed:
        persistent_notification.create(
            hass,
            "Error: Failed to obtain an access token from the cached "
            "refresh token.<br />"
            "Token may have expired or been revoked.<br />"
            "Please unload then re-add the Logi Circle integration to resolve",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False
    except asyncio.TimeoutError:
        # The TimeoutError exception object returns nothing when casted to a
        # string, so we'll handle it separately.
        err = f"{_TIMEOUT}s timeout exceeded when connecting to Logi Circle API"
        persistent_notification.create(
            hass,
            f"Error: {err}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False
    except ClientResponseError as ex:
        persistent_notification.create(
            hass,
            f"Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    hass.data[DATA_LOGI] = logi_circle

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def service_handler(service: ServiceCall) -> None:
        """Dispatch service calls to target entities."""
        params = dict(service.data)

        if service.service == SERVICE_SET_CONFIG:
            async_dispatcher_send(hass, SIGNAL_LOGI_CIRCLE_RECONFIGURE, params)
        if service.service == SERVICE_LIVESTREAM_SNAPSHOT:
            async_dispatcher_send(hass, SIGNAL_LOGI_CIRCLE_SNAPSHOT, params)
        if service.service == SERVICE_LIVESTREAM_RECORD:
            async_dispatcher_send(hass, SIGNAL_LOGI_CIRCLE_RECORD, params)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CONFIG,
        service_handler,
        schema=LOGI_CIRCLE_SERVICE_SET_CONFIG,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIVESTREAM_SNAPSHOT,
        service_handler,
        schema=LOGI_CIRCLE_SERVICE_SNAPSHOT,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIVESTREAM_RECORD,
        service_handler,
        schema=LOGI_CIRCLE_SERVICE_RECORD,
    )

    async def shut_down(event=None):
        """Close Logi Circle aiohttp session."""
        await logi_circle.auth_provider.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shut_down)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    logi_circle = hass.data.pop(DATA_LOGI)

    # Tell API wrapper to close all aiohttp sessions, invalidate WS connections
    # and clear all locally cached tokens
    await logi_circle.auth_provider.clear_authorization()

    return unload_ok
