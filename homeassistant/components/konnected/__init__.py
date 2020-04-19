"""Support for Konnected devices."""
import asyncio
import copy
import hmac
import json
import logging

from aiohttp.hdrs import AUTHORIZATION
from aiohttp.web import Request, Response
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ACCESS_TOKEN,
    CONF_BINARY_SENSORS,
    CONF_DEVICES,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PIN,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_TYPE,
    CONF_ZONE,
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
    HTTP_UNAUTHORIZED,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .config_flow import (  # Loading the config flow file will register the flow
    CONF_DEFAULT_OPTIONS,
    CONF_IO,
    CONF_IO_BIN,
    CONF_IO_DIG,
    CONF_IO_SWI,
    OPTIONS_SCHEMA,
)
from .const import (
    CONF_ACTIVATION,
    CONF_API_HOST,
    CONF_BLINK,
    CONF_DISCOVERY,
    CONF_INVERSE,
    CONF_MOMENTARY,
    CONF_PAUSE,
    CONF_POLL_INTERVAL,
    CONF_REPEAT,
    DOMAIN,
    PIN_TO_ZONE,
    STATE_HIGH,
    STATE_LOW,
    UNDO_UPDATE_LISTENER,
    UPDATE_ENDPOINT,
    ZONE_TO_PIN,
    ZONES,
)
from .errors import CannotConnect
from .handlers import HANDLERS
from .panel import AlarmPanel

_LOGGER = logging.getLogger(__name__)


def ensure_pin(value):
    """Check if valid pin and coerce to string."""
    if value is None:
        raise vol.Invalid("pin value is None")

    if PIN_TO_ZONE.get(str(value)) is None:
        raise vol.Invalid("pin not valid")

    return str(value)


def ensure_zone(value):
    """Check if valid zone and coerce to string."""
    if value is None:
        raise vol.Invalid("zone value is None")

    if str(value) not in ZONES is None:
        raise vol.Invalid("zone not valid")

    return str(value)


def import_device_validator(config):
    """Validate zones and reformat for import."""
    config = copy.deepcopy(config)
    io_cfgs = {}
    # Replace pins with zones
    for conf_platform, conf_io in (
        (CONF_BINARY_SENSORS, CONF_IO_BIN),
        (CONF_SENSORS, CONF_IO_DIG),
        (CONF_SWITCHES, CONF_IO_SWI),
    ):
        for zone in config.get(conf_platform, []):
            if zone.get(CONF_PIN):
                zone[CONF_ZONE] = PIN_TO_ZONE[zone[CONF_PIN]]
                del zone[CONF_PIN]
            io_cfgs[zone[CONF_ZONE]] = conf_io

    # Migrate config_entry data into default_options structure
    config[CONF_IO] = io_cfgs
    config[CONF_DEFAULT_OPTIONS] = OPTIONS_SCHEMA(config)

    # clean up fields migrated to options
    config.pop(CONF_BINARY_SENSORS, None)
    config.pop(CONF_SENSORS, None)
    config.pop(CONF_SWITCHES, None)
    config.pop(CONF_BLINK, None)
    config.pop(CONF_DISCOVERY, None)
    config.pop(CONF_API_HOST, None)
    config.pop(CONF_IO, None)
    return config


def import_validator(config):
    """Reformat for import."""
    config = copy.deepcopy(config)

    # push api_host into device configs
    for device in config.get(CONF_DEVICES, []):
        device[CONF_API_HOST] = config.get(CONF_API_HOST, "")

    return config


# configuration.yaml schemas (legacy)
BINARY_SENSOR_SCHEMA_YAML = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_ZONE, "s_io"): ensure_zone,
            vol.Exclusive(CONF_PIN, "s_io"): ensure_pin,
            vol.Required(CONF_TYPE): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_INVERSE, default=False): cv.boolean,
        }
    ),
    cv.has_at_least_one_key(CONF_PIN, CONF_ZONE),
)

SENSOR_SCHEMA_YAML = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_ZONE, "s_io"): ensure_zone,
            vol.Exclusive(CONF_PIN, "s_io"): ensure_pin,
            vol.Required(CONF_TYPE): vol.All(vol.Lower, vol.In(["dht", "ds18b20"])),
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_POLL_INTERVAL, default=3): vol.All(
                vol.Coerce(int), vol.Range(min=1)
            ),
        }
    ),
    cv.has_at_least_one_key(CONF_PIN, CONF_ZONE),
)

SWITCH_SCHEMA_YAML = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_ZONE, "s_io"): ensure_zone,
            vol.Exclusive(CONF_PIN, "s_io"): ensure_pin,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_ACTIVATION, default=STATE_HIGH): vol.All(
                vol.Lower, vol.Any(STATE_HIGH, STATE_LOW)
            ),
            vol.Optional(CONF_MOMENTARY): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Optional(CONF_PAUSE): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Optional(CONF_REPEAT): vol.All(vol.Coerce(int), vol.Range(min=-1)),
        }
    ),
    cv.has_at_least_one_key(CONF_PIN, CONF_ZONE),
)

DEVICE_SCHEMA_YAML = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_ID): cv.matches_regex("[0-9a-f]{12}"),
            vol.Optional(CONF_BINARY_SENSORS): vol.All(
                cv.ensure_list, [BINARY_SENSOR_SCHEMA_YAML]
            ),
            vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [SENSOR_SCHEMA_YAML]),
            vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [SWITCH_SCHEMA_YAML]),
            vol.Inclusive(CONF_HOST, "host_info"): cv.string,
            vol.Inclusive(CONF_PORT, "host_info"): cv.port,
            vol.Optional(CONF_BLINK, default=True): cv.boolean,
            vol.Optional(CONF_API_HOST, default=""): vol.Any("", cv.url),
            vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
        }
    ),
    import_device_validator,
)

# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            import_validator,
            vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): cv.string,
                    vol.Optional(CONF_API_HOST): vol.Url(),
                    vol.Optional(CONF_DEVICES): vol.All(
                        cv.ensure_list, [DEVICE_SCHEMA_YAML]
                    ),
                }
            ),
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

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            CONF_ACCESS_TOKEN: cfg.get(CONF_ACCESS_TOKEN),
            CONF_API_HOST: cfg.get(CONF_API_HOST),
            CONF_DEVICES: {},
        }

    hass.http.register_view(KonnectedView)

    # Check if they have yaml configured devices
    if CONF_DEVICES not in cfg:
        return True

    for device in cfg.get(CONF_DEVICES, []):
        # Attempt to importing the cfg. Use
        # hass.async_add_job to avoid a deadlock.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=device
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up panel from a config entry."""
    client = AlarmPanel(hass, entry)
    # creates a panel data store in hass.data[DOMAIN][CONF_DEVICES]
    await client.async_save_data()

    try:
        await client.async_connect()
    except CannotConnect:
        # this will trigger a retry in the future
        raise config_entries.ConfigEntryNotReady

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    # config entry specific data to enable unload
    hass.data[DOMAIN][entry.entry_id] = {
        UNDO_UPDATE_LISTENER: entry.add_update_listener(async_entry_updated)
    }
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

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN][CONF_DEVICES].pop(entry.data[CONF_ID])
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_entry_updated(hass: HomeAssistant, entry: ConfigEntry):
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


class KonnectedView(HomeAssistantView):
    """View creates an endpoint to receive push updates from the device."""

    url = UPDATE_ENDPOINT
    name = "api:konnected"
    requires_auth = False  # Uses access token from configuration

    def __init__(self):
        """Initialize the view."""

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

        auth = request.headers.get(AUTHORIZATION)
        tokens = []
        if hass.data[DOMAIN].get(CONF_ACCESS_TOKEN):
            tokens.extend([hass.data[DOMAIN][CONF_ACCESS_TOKEN]])
        tokens.extend(
            [
                entry.data[CONF_ACCESS_TOKEN]
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.data.get(CONF_ACCESS_TOKEN)
            ]
        )
        if auth is None or not next(
            (True for token in tokens if hmac.compare_digest(f"Bearer {token}", auth)),
            False,
        ):
            return self.json_message("unauthorized", status_code=HTTP_UNAUTHORIZED)

        try:  # Konnected 2.2.0 and above supports JSON payloads
            payload = await request.json()
        except json.decoder.JSONDecodeError:
            _LOGGER.error(
                "Your Konnected device software may be out of "
                "date. Visit https://help.konnected.io for "
                "updating instructions."
            )

        device = data[CONF_DEVICES].get(device_id)
        if device is None:
            return self.json_message(
                "unregistered device", status_code=HTTP_BAD_REQUEST
            )

        try:
            zone_num = str(payload.get(CONF_ZONE) or PIN_TO_ZONE[payload[CONF_PIN]])
            payload[CONF_ZONE] = zone_num
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
                f"Device {device_id} not configured", status_code=HTTP_NOT_FOUND
            )

        # Our data model is based on zone ids but we convert from/to pin ids
        # based on whether they are specified in the request
        try:
            zone_num = str(
                request.query.get(CONF_ZONE) or PIN_TO_ZONE[request.query[CONF_PIN]]
            )
            zone = next(
                switch
                for switch in device[CONF_SWITCHES]
                if switch[CONF_ZONE] == zone_num
            )

        except StopIteration:
            zone = None
        except KeyError:
            zone = None
            zone_num = None

        if not zone:
            target = request.query.get(
                CONF_ZONE, request.query.get(CONF_PIN, "unknown")
            )
            return self.json_message(
                f"Switch on zone or pin {target} not configured",
                status_code=HTTP_NOT_FOUND,
            )

        resp = {}
        if request.query.get(CONF_ZONE):
            resp[CONF_ZONE] = zone_num
        else:
            resp[CONF_PIN] = ZONE_TO_PIN[zone_num]

        # Make sure entity is setup
        zone_entity_id = zone.get(ATTR_ENTITY_ID)
        if zone_entity_id:
            resp["state"] = self.binary_value(
                hass.states.get(zone_entity_id).state, zone[CONF_ACTIVATION]
            )
            return self.json(resp)

        _LOGGER.warning("Konnected entity not yet setup, returning default")
        resp["state"] = self.binary_value(STATE_OFF, zone[CONF_ACTIVATION])
        return self.json(resp)

    async def put(self, request: Request, device_id) -> Response:
        """Receive a sensor update via PUT request and async set state."""
        return await self.update_sensor(request, device_id)

    async def post(self, request: Request, device_id) -> Response:
        """Receive a sensor update via POST request and async set state."""
        return await self.update_sensor(request, device_id)
