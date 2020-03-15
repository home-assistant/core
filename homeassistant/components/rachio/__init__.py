"""Integration with the Rachio Iro sprinkler system controller."""
import asyncio
import logging
import secrets
from typing import Optional

from aiohttp import web
from rachiopy import Rachio
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, EVENT_HOMEASSISTANT_STOP, URL_API
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_CUSTOM_URL,
    CONF_MANUAL_RUN_MINS,
    DEFAULT_MANUAL_RUN_MINS,
    DEFAULT_NAME,
    DOMAIN,
    KEY_DEVICES,
    KEY_ENABLED,
    KEY_EXTERNAL_ID,
    KEY_ID,
    KEY_MAC_ADDRESS,
    KEY_MODEL,
    KEY_NAME,
    KEY_SERIAL_NUMBER,
    KEY_STATUS,
    KEY_TYPE,
    KEY_USERNAME,
    KEY_ZONES,
    RACHIO_API_EXCEPTIONS,
)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_DOMAINS = ["switch", "binary_sensor"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_CUSTOM_URL): cv.string,
                vol.Optional(
                    CONF_MANUAL_RUN_MINS, default=DEFAULT_MANUAL_RUN_MINS
                ): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


STATUS_ONLINE = "ONLINE"
STATUS_OFFLINE = "OFFLINE"

# Device webhook values
TYPE_CONTROLLER_STATUS = "DEVICE_STATUS"
SUBTYPE_OFFLINE = "OFFLINE"
SUBTYPE_ONLINE = "ONLINE"
SUBTYPE_OFFLINE_NOTIFICATION = "OFFLINE_NOTIFICATION"
SUBTYPE_COLD_REBOOT = "COLD_REBOOT"
SUBTYPE_SLEEP_MODE_ON = "SLEEP_MODE_ON"
SUBTYPE_SLEEP_MODE_OFF = "SLEEP_MODE_OFF"
SUBTYPE_BROWNOUT_VALVE = "BROWNOUT_VALVE"
SUBTYPE_RAIN_SENSOR_DETECTION_ON = "RAIN_SENSOR_DETECTION_ON"
SUBTYPE_RAIN_SENSOR_DETECTION_OFF = "RAIN_SENSOR_DETECTION_OFF"
SUBTYPE_RAIN_DELAY_ON = "RAIN_DELAY_ON"
SUBTYPE_RAIN_DELAY_OFF = "RAIN_DELAY_OFF"

# Schedule webhook values
TYPE_SCHEDULE_STATUS = "SCHEDULE_STATUS"
SUBTYPE_SCHEDULE_STARTED = "SCHEDULE_STARTED"
SUBTYPE_SCHEDULE_STOPPED = "SCHEDULE_STOPPED"
SUBTYPE_SCHEDULE_COMPLETED = "SCHEDULE_COMPLETED"
SUBTYPE_WEATHER_NO_SKIP = "WEATHER_INTELLIGENCE_NO_SKIP"
SUBTYPE_WEATHER_SKIP = "WEATHER_INTELLIGENCE_SKIP"
SUBTYPE_WEATHER_CLIMATE_SKIP = "WEATHER_INTELLIGENCE_CLIMATE_SKIP"
SUBTYPE_WEATHER_FREEZE = "WEATHER_INTELLIGENCE_FREEZE"

# Zone webhook values
TYPE_ZONE_STATUS = "ZONE_STATUS"
SUBTYPE_ZONE_STARTED = "ZONE_STARTED"
SUBTYPE_ZONE_STOPPED = "ZONE_STOPPED"
SUBTYPE_ZONE_COMPLETED = "ZONE_COMPLETED"
SUBTYPE_ZONE_CYCLING = "ZONE_CYCLING"
SUBTYPE_ZONE_CYCLING_COMPLETED = "ZONE_CYCLING_COMPLETED"

# Webhook callbacks
LISTEN_EVENT_TYPES = ["DEVICE_STATUS_EVENT", "ZONE_STATUS_EVENT"]
WEBHOOK_CONST_ID = "homeassistant.rachio:"
WEBHOOK_PATH = URL_API + DOMAIN
SIGNAL_RACHIO_UPDATE = DOMAIN + "_update"
SIGNAL_RACHIO_CONTROLLER_UPDATE = SIGNAL_RACHIO_UPDATE + "_controller"
SIGNAL_RACHIO_ZONE_UPDATE = SIGNAL_RACHIO_UPDATE + "_zone"
SIGNAL_RACHIO_SCHEDULE_UPDATE = SIGNAL_RACHIO_UPDATE + "_schedule"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the rachio component from YAML."""

    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in SUPPORTED_DOMAINS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Rachio config entry."""

    config = entry.data
    options = entry.options

    # CONF_MANUAL_RUN_MINS can only come from a yaml import
    if not options.get(CONF_MANUAL_RUN_MINS) and config.get(CONF_MANUAL_RUN_MINS):
        options_copy = options.copy()
        options_copy[CONF_MANUAL_RUN_MINS] = config[CONF_MANUAL_RUN_MINS]
        hass.config_entries.async_update_entry(options=options_copy)

    # Configure API
    api_key = config[CONF_API_KEY]
    rachio = Rachio(api_key)

    # Get the URL of this server
    custom_url = config.get(CONF_CUSTOM_URL)
    hass_url = hass.config.api.base_url if custom_url is None else custom_url
    rachio.webhook_auth = secrets.token_hex()
    webhook_url_path = f"{WEBHOOK_PATH}-{entry.entry_id}"
    rachio.webhook_url = f"{hass_url}{webhook_url_path}"

    person = RachioPerson(rachio, entry)

    # Get the API user
    try:
        await hass.async_add_executor_job(person.setup, hass)
    # Yes we really do get all these exceptions (hopefully rachiopy switches to requests)
    # and there is not a reasonable timeout here so it can block for a long time
    except RACHIO_API_EXCEPTIONS as error:
        _LOGGER.error("Could not reach the Rachio API: %s", error)
        raise ConfigEntryNotReady

    # Check for Rachio controller devices
    if not person.controllers:
        _LOGGER.error("No Rachio devices found in account %s", person.username)
        return False
    _LOGGER.info("%d Rachio device(s) found", len(person.controllers))

    # Enable component
    hass.data[DOMAIN][entry.entry_id] = person

    # Listen for incoming webhook connections after the data is there
    hass.http.register_view(RachioWebhookView(entry.entry_id, webhook_url_path))

    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


class RachioPerson:
    """Represent a Rachio user."""

    def __init__(self, rachio, config_entry):
        """Create an object from the provided API instance."""
        # Use API token to get user ID
        self.rachio = rachio
        self.config_entry = config_entry
        self.username = None
        self._id = None
        self._controllers = []

    def setup(self, hass):
        """Rachio device setup."""
        response = self.rachio.person.getInfo()
        assert int(response[0][KEY_STATUS]) == 200, "API key error"
        self._id = response[1][KEY_ID]

        # Use user ID to get user data
        data = self.rachio.person.get(self._id)
        assert int(data[0][KEY_STATUS]) == 200, "User ID error"
        self.username = data[1][KEY_USERNAME]
        devices = data[1][KEY_DEVICES]
        for controller in devices:
            webhooks = self.rachio.notification.getDeviceWebhook(controller[KEY_ID])[1]
            # The API does not provide a way to tell if a controller is shared
            # or if they are the owner. To work around this problem we fetch the webooks
            # before we setup the device so we can skip it instead of failing.
            # webhooks are normally a list, however if there is an error
            # rachio hands us back a dict
            if isinstance(webhooks, dict):
                _LOGGER.error(
                    "Failed to add rachio controller '%s' because of an error: %s",
                    controller[KEY_NAME],
                    webhooks.get("error", "Unknown Error"),
                )
                continue

            rachio_iro = RachioIro(hass, self.rachio, controller, webhooks)
            rachio_iro.setup()
            self._controllers.append(rachio_iro)
        _LOGGER.info('Using Rachio API as user "%s"', self.username)

    @property
    def user_id(self) -> str:
        """Get the user ID as defined by the Rachio API."""
        return self._id

    @property
    def controllers(self) -> list:
        """Get a list of controllers managed by this account."""
        return self._controllers


class RachioIro:
    """Represent a Rachio Iro."""

    def __init__(self, hass, rachio, data, webhooks):
        """Initialize a Rachio device."""
        self.hass = hass
        self.rachio = rachio
        self._id = data[KEY_ID]
        self.name = data[KEY_NAME]
        self.serial_number = data[KEY_SERIAL_NUMBER]
        self.mac_address = data[KEY_MAC_ADDRESS]
        self.model = data[KEY_MODEL]
        self._zones = data[KEY_ZONES]
        self._init_data = data
        self._webhooks = webhooks
        _LOGGER.debug('%s has ID "%s"', str(self), self.controller_id)

    def setup(self):
        """Rachio Iro setup for webhooks."""
        # Listen for all updates
        self._init_webhooks()

    def _init_webhooks(self) -> None:
        """Start getting updates from the Rachio API."""
        current_webhook_id = None

        # First delete any old webhooks that may have stuck around
        def _deinit_webhooks(event) -> None:
            """Stop getting updates from the Rachio API."""
            if not self._webhooks:
                # We fetched webhooks when we created the device, however if we call _init_webhooks
                # again we need to fetch again
                self._webhooks = self.rachio.notification.getDeviceWebhook(
                    self.controller_id
                )[1]
            for webhook in self._webhooks:
                if (
                    webhook[KEY_EXTERNAL_ID].startswith(WEBHOOK_CONST_ID)
                    or webhook[KEY_ID] == current_webhook_id
                ):
                    self.rachio.notification.deleteWebhook(webhook[KEY_ID])
            self._webhooks = None

        _deinit_webhooks(None)

        # Choose which events to listen for and get their IDs
        event_types = []
        for event_type in self.rachio.notification.getWebhookEventType()[1]:
            if event_type[KEY_NAME] in LISTEN_EVENT_TYPES:
                event_types.append({"id": event_type[KEY_ID]})

        # Register to listen to these events from the device
        url = self.rachio.webhook_url
        auth = WEBHOOK_CONST_ID + self.rachio.webhook_auth
        new_webhook = self.rachio.notification.postWebhook(
            self.controller_id, auth, url, event_types
        )
        # Save ID for deletion at shutdown
        current_webhook_id = new_webhook[1][KEY_ID]
        self.hass.bus.listen(EVENT_HOMEASSISTANT_STOP, _deinit_webhooks)

    def __str__(self) -> str:
        """Display the controller as a string."""
        return f'Rachio controller "{self.name}"'

    @property
    def controller_id(self) -> str:
        """Return the Rachio API controller ID."""
        return self._id

    @property
    def current_schedule(self) -> str:
        """Return the schedule that the device is running right now."""
        return self.rachio.device.getCurrentSchedule(self.controller_id)[1]

    @property
    def init_data(self) -> dict:
        """Return the information used to set up the controller."""
        return self._init_data

    def list_zones(self, include_disabled=False) -> list:
        """Return a list of the zone dicts connected to the device."""
        # All zones
        if include_disabled:
            return self._zones

        # Only enabled zones
        return [z for z in self._zones if z[KEY_ENABLED]]

    def get_zone(self, zone_id) -> Optional[dict]:
        """Return the zone with the given ID."""
        for zone in self.list_zones(include_disabled=True):
            if zone[KEY_ID] == zone_id:
                return zone

        return None

    def stop_watering(self) -> None:
        """Stop watering all zones connected to this controller."""
        self.rachio.device.stopWater(self.controller_id)
        _LOGGER.info("Stopped watering of all zones on %s", str(self))


class RachioDeviceInfoProvider(Entity):
    """Mixin to provide device_info."""

    def __init__(self, controller):
        """Initialize a Rachio device."""
        super().__init__()
        self._controller = controller

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._controller.serial_number,)},
            "connections": {
                (device_registry.CONNECTION_NETWORK_MAC, self._controller.mac_address,)
            },
            "name": self._controller.name,
            "model": self._controller.model,
            "manufacturer": DEFAULT_NAME,
        }


class RachioWebhookView(HomeAssistantView):
    """Provide a page for the server to call."""

    SIGNALS = {
        TYPE_CONTROLLER_STATUS: SIGNAL_RACHIO_CONTROLLER_UPDATE,
        TYPE_SCHEDULE_STATUS: SIGNAL_RACHIO_SCHEDULE_UPDATE,
        TYPE_ZONE_STATUS: SIGNAL_RACHIO_ZONE_UPDATE,
    }

    requires_auth = False  # Handled separately

    def __init__(self, entry_id, webhook_url):
        """Initialize the instance of the view."""
        self._entry_id = entry_id
        self.url = webhook_url
        self.name = webhook_url[1:].replace("/", ":")
        _LOGGER.debug(
            "Initialize webhook at url: %s, with name %s", self.url, self.name
        )

    async def post(self, request) -> web.Response:
        """Handle webhook calls from the server."""
        hass = request.app["hass"]
        data = await request.json()

        try:
            auth = data.get(KEY_EXTERNAL_ID, str()).split(":")[1]
            assert auth == hass.data[DOMAIN][self._entry_id].rachio.webhook_auth
        except (AssertionError, IndexError):
            return web.Response(status=web.HTTPForbidden.status_code)

        update_type = data[KEY_TYPE]
        if update_type in self.SIGNALS:
            async_dispatcher_send(hass, self.SIGNALS[update_type], data)

        return web.Response(status=web.HTTPNoContent.status_code)
