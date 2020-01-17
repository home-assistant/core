"""Support for Konnected devices."""
import asyncio
import hmac
import json
import logging
import random
import string

from aiohttp.hdrs import AUTHORIZATION
from aiohttp.web import Request, Response
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ACCESS_TOKEN,
    CONF_BINARY_SENSORS,
    CONF_DEVICES,
    CONF_ID,
    CONF_PIN,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_ZONE,
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
    HTTP_UNAUTHORIZED,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, storage

from .config_flow import (  # Loading the config flow file will register the flow
    DEVICE_SCHEMA_YAML,
    configured_devices,
)
from .const import (
    CONF_ACTIVATION,
    CONF_API_HOST,
    DOMAIN,
    PIN_TO_ZONE,
    STATE_HIGH,
    UPDATE_ENDPOINT,
    ZONE_TO_PIN,
)
from .errors import CannotConnect
from .handlers import HANDLERS
from .panel import AlarmPanel

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN

# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(CONF_API_HOST): vol.Url(),
                vol.Optional(CONF_DEVICES): [DEVICE_SCHEMA_YAML],
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

YAML_CONFIGS = "yaml_configs"
PLATFORMS = ["binary_sensor", "sensor", "switch"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Konnected platform."""
    cfg = config.get(DOMAIN)
    if cfg is None:
        cfg = {}

    store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data_store = await store.async_load()
    if data_store is None:
        data_store = {}

    # create a token if none in yaml or storage
    access_token = (
        cfg.get(CONF_ACCESS_TOKEN)
        or data_store.get(CONF_ACCESS_TOKEN)
        or "".join(random.choices(string.ascii_uppercase + string.digits, k=20))
    )
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            CONF_ACCESS_TOKEN: access_token,
            CONF_API_HOST: cfg.get(CONF_API_HOST),
            CONF_DEVICES: {},
            "config_data": {},
        }

    # save off the access token
    await store.async_save({CONF_ACCESS_TOKEN: access_token})

    hass.http.register_view(KonnectedView(access_token))

    # Check if they have yaml configured devices
    if CONF_DEVICES not in cfg:
        return True

    configured = configured_devices(hass)
    devices = cfg[CONF_DEVICES]

    if devices:
        for device in devices:
            # If configured, the panel is already imported and needs to be managed via config entries
            if device["id"] in configured:
                continue

            # No existing config entry found, try importing it. Use
            # hass.async_add_job to avoid a deadlock.
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=device,
                )
            )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up panel from a config entry."""
    try:
        device_data = hass.data[DOMAIN][CONF_DEVICES].get(entry.data["id"])
        if device_data:
            client = device_data["panel"]
        else:
            client = AlarmPanel(hass, entry)
            await client.async_save_data()

        await client.async_connect()
        for component in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )

    except CannotConnect:
        # this will trigger a retry in the future
        raise config_entries.ConfigEntryNotReady

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][CONF_DEVICES].pop(entry.data[CONF_ID])

    return unload_ok


class KonnectedView(HomeAssistantView):
    """View creates an endpoint to receive push updates from the device."""

    url = UPDATE_ENDPOINT
    name = "api:konnected"
    requires_auth = False  # Uses access token from configuration

    def __init__(self, auth_token):
        """Initialize the view."""
        self.auth_token = auth_token

    @staticmethod
    def binary_value(state, activation):
        """Return binary value for GPIO based on state and activation."""
        if activation == STATE_HIGH:
            return 1 if state == STATE_ON else 0
        return 0 if state == STATE_ON else 1

    async def update_sensor(self, request: Request, device_id) -> Response:
        """Process a put or post."""
        hass = request.app["hass"]
        data = hass.data[DOMAIN]

        auth = request.headers.get(AUTHORIZATION, None)
        if auth is None or not hmac.compare_digest(f"Bearer {self.auth_token}", auth):
            return self.json_message("unauthorized", status_code=HTTP_UNAUTHORIZED)

        try:  # Konnected 2.2.0 and above supports JSON payloads
            payload = await request.json()
        except json.decoder.JSONDecodeError:
            _LOGGER.error(
                (
                    "Your Konnected device software may be out of "
                    "date. Visit https://help.konnected.io for "
                    "updating instructions."
                )
            )

        device = data[CONF_DEVICES].get(device_id)
        if device is None:
            return self.json_message(
                "unregistered device", status_code=HTTP_BAD_REQUEST
            )

        try:
            zone_num = str(payload.get(CONF_ZONE) or PIN_TO_ZONE[payload[CONF_PIN]])
            zone_data = device[CONF_BINARY_SENSORS].get(zone_num) or next(
                (s for s in device[CONF_SENSORS] if s[CONF_ZONE] == zone_num), None
            )
        except KeyError:
            zone_data = None

        if zone_data is None:
            return self.json_message(
                "unregistered sensor/actuator", status_code=HTTP_BAD_REQUEST
            )

        zone_data["device_id"] = device_id

        for attr in ["state", "temp", "humi", "addr"]:
            value = payload.get(attr)
            handler = HANDLERS.get(attr)
            if value is not None and handler:
                hass.async_create_task(handler(hass, zone_data, payload))

        return self.json_message("ok")

    async def get(self, request: Request, device_id) -> Response:
        """Return the current binary state of a switch."""
        hass = request.app["hass"]
        data = hass.data[DOMAIN]

        device = data[CONF_DEVICES].get(device_id)
        if not device:
            return self.json_message(
                "Device " + device_id + " not configured", status_code=HTTP_NOT_FOUND
            )

        # Our data model is based on zone ids but we convert from/to pin ids
        # based on whether they are specified in the request
        try:
            zone_num = str(
                request.query.get(CONF_ZONE) or PIN_TO_ZONE[request.query[CONF_PIN]]
            )
            zone = next(
                filter(
                    lambda switch: switch[CONF_ZONE] == zone_num, device[CONF_SWITCHES]
                )
            )
        except StopIteration:
            zone = None
        except KeyError:
            zone = None
            zone_num = None

        if not zone:
            return self.json_message(
                "Switch on zone or pin {} not configured".format(
                    request.query.get(CONF_ZONE)
                    or request.query.get(CONF_PIN, "unknown")
                ),
                status_code=HTTP_NOT_FOUND,
            )

        resp = {}
        if request.query.get(CONF_ZONE):
            resp.update({CONF_ZONE: zone_num})
        else:
            resp.update({CONF_PIN: ZONE_TO_PIN[zone_num]})

        # Make sure entity is setup
        if zone.get(ATTR_ENTITY_ID):
            resp.update(
                {
                    "state": self.binary_value(
                        hass.states.get(zone.get(ATTR_ENTITY_ID)).state,
                        zone[CONF_ACTIVATION],
                    ),
                }
            )
            return self.json(resp)

        _LOGGER.warning("Konnected entity not yet setup, returning default")
        resp.update({"state": self.binary_value(STATE_OFF, zone[CONF_ACTIVATION])})
        return self.json(resp)

    async def put(self, request: Request, device_id) -> Response:
        """Receive a sensor update via PUT request and async set state."""
        return await self.update_sensor(request, device_id)

    async def post(self, request: Request, device_id) -> Response:
        """Receive a sensor update via POST request and async set state."""
        return await self.update_sensor(request, device_id)
