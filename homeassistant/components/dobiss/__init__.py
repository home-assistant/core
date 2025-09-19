"""The dobiss integration."""

from asyncio import gather
import logging
from typing import Any

from dobissapi import DobissAPI
import voluptuous as vol

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import entity_ids
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_COVER_CLOSETIME,
    CONF_COVER_SET_END_POSITION,
    CONF_COVER_USE_TIMED,
    CONF_IGNORE_ZIGBEE_DEVICES,
    CONF_INVERT_BINARY_SENSOR,
    CONF_WEBSOCKET_TIMEOUT,
    DEFAULT_COVER_CLOSETIME,
    DEFAULT_COVER_SET_END_POSITION,
    DEFAULT_COVER_USE_TIMED,
    DEFAULT_IGNORE_ZIGBEE_DEVICES,
    DEFAULT_INVERT_BINARY_SENSOR,
    DEFAULT_WEBSOCKET_TIMEOUT,
    DEVICES,
    DOMAIN,
    KEY_API,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]

SERVICE_ACTION_REQUEST = "action_request"
SERVICE_STATUS_REQUEST = "status_request"
SERVICE_FORCE_UPDATE = "force_update"
SERVICE_TURN_ON = "turn_on"

ATTR_ADDRESS = "address"
ATTR_CHANNEL = "channel"
ATTR_ACTION = "action"
ATTR_OPTION1 = "option1"
ATTR_OPTION2 = "option2"
ATTR_DELAYON = "delayon"
ATTR_DELAYOFF = "delayoff"
ATTR_FROMPIR = "from_pir"

ACTION_REQUEST_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(ATTR_ADDRESS): vol.Coerce(int),
            vol.Required(ATTR_CHANNEL): vol.Coerce(int),
            vol.Required(ATTR_ACTION): vol.Coerce(int),
            vol.Optional(ATTR_OPTION1): vol.Any(int),
            vol.Optional(ATTR_OPTION2): vol.Any(int),
        }
    )
)
STATUS_REQUEST_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(ATTR_ADDRESS): vol.Coerce(int),
            vol.Optional(ATTR_CHANNEL): vol.Coerce(int),
        }
    )
)
TURN_ON_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(ATTR_ENTITY_ID): vol.Coerce(entity_ids),
            vol.Optional(ATTR_BRIGHTNESS): vol.Coerce(int),
            vol.Optional(ATTR_DELAYON): vol.Coerce(int),
            vol.Optional(ATTR_DELAYOFF): vol.Coerce(int),
            vol.Optional(ATTR_FROMPIR): cv.boolean,
        }
    )
)

SERVICE_TO_METHOD = {
    SERVICE_TURN_ON: {"method": "turn_on_service", "schema": TURN_ON_SCHEMA}
}

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the dobiss component."""
    _LOGGER.warning("DOBISS INTEGRATIE WORDT GELADEN")
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up dobiss from a config entry."""

    _LOGGER.debug("async_setup_entry")
    client = HADobiss(hass, entry)
    entry.runtime_data = client
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {KEY_API: client}

    if not await client.async_setup():
        _LOGGER.warning("Dobiss setup failed")
        return False

    # entry.add_update_listener(async_reload_entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry")
    if hass.data[DOMAIN][entry.entry_id][KEY_API].unsub:
        hass.data[DOMAIN][entry.entry_id][KEY_API].unsub()
    unload_ok = all(
        await gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    else:
        _LOGGER.warning("Unload failed")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class HADobiss:
    """Handle communication and setup logic for a single Dobiss config entry."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Dobiss data."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = None
        self.available = False
        self.unsub = None
        self.devices: list[Any] = []

    @property
    def host(self):
        """Return client host."""
        return self.config_entry.data[CONF_HOST]

    async def async_setup(self):
        """Set up the Dobiss client."""
        try:
            self.api = DobissAPI(
                self.config_entry.data["secret"],
                self.config_entry.data["host"],
                self.config_entry.data["secure"],
            )
            websocket_timeout = self.config_entry.options.get(
                CONF_WEBSOCKET_TIMEOUT, DEFAULT_WEBSOCKET_TIMEOUT
            )
            _LOGGER.debug(
                "(async_setup) Setting websocket timeout to %s", websocket_timeout
            )

            if websocket_timeout == 0:
                self.api.websocket_timeout = None
            else:
                self.api.websocket_timeout = websocket_timeout
            devices = self.api.get_all_devices()
            self.hass.data[DOMAIN][self.config_entry.entry_id][DEVICES] = devices

            # logger.setLevel(logging.DEBUG)
            await self.api.discovery()
            self.hass.async_create_task(self.api.dobiss_monitor())

            self.available = True
            _LOGGER.debug("Successfully connected to Dobiss")

        except Exception as err:
            _LOGGER.exception("Can not connect to Dobiss")
            self.available = False
            raise ConfigEntryNotReady from err

        self.add_options()
        self.unsub = self.config_entry.add_update_listener(self.update_listener)

        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, PLATFORMS
        )

        async def handle_action_request(call):
            """Handle action_request service."""
            dobiss = self.api
            writedata = {
                ATTR_ADDRESS: call.data.get(ATTR_ADDRESS),
                ATTR_CHANNEL: call.data.get(ATTR_CHANNEL),
                ATTR_ACTION: call.data.get(ATTR_ACTION),
            }
            if ATTR_OPTION1 in call.data:
                writedata[ATTR_OPTION1] = call.data.get(ATTR_OPTION1)
            if ATTR_OPTION2 in call.data:
                writedata[ATTR_OPTION2] = call.data.get(ATTR_OPTION2)
            _LOGGER.info("Sending action request %s", writedata)
            response = await dobiss.request(writedata)
            _LOGGER.info(await response.json())

        async def handle_status_request(call):
            """Handle status_request service."""
            dobiss = self.api
            response = await dobiss.status(
                call.data.get(ATTR_ADDRESS), call.data.get(ATTR_CHANNEL)
            )
            _LOGGER.info(await response.json())

        async def handle_force_update(call):
            """Handle status_request service."""
            dobiss = self.api
            await dobiss.update_all(force=True)

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_FORCE_UPDATE,
            handle_force_update,
        )
        self.hass.services.async_register(
            DOMAIN,
            SERVICE_ACTION_REQUEST,
            handle_action_request,
            schema=ACTION_REQUEST_SCHEMA,
        )
        self.hass.services.async_register(
            DOMAIN,
            SERVICE_STATUS_REQUEST,
            handle_status_request,
            schema=STATUS_REQUEST_SCHEMA,
        )

        async def service_handler(service):
            method = SERVICE_TO_METHOD.get(service.service)
            data = service.data.copy()
            data["method"] = method["method"]
            async_dispatcher_send(self.hass, DOMAIN, data)

        for service_name, service_data in SERVICE_TO_METHOD.items():
            self.hass.services.async_register(
                DOMAIN,
                service_name,
                service_handler,
                schema=service_data["schema"],
            )

        return True

    def add_options(self):
        """Add options for dobiss integration."""
        options = (
            self.config_entry.options.copy()
            if self.config_entry.options is not None
            else {}
        )
        if CONF_INVERT_BINARY_SENSOR not in options:
            options[CONF_INVERT_BINARY_SENSOR] = DEFAULT_INVERT_BINARY_SENSOR
        if CONF_IGNORE_ZIGBEE_DEVICES not in options:
            options[CONF_IGNORE_ZIGBEE_DEVICES] = DEFAULT_IGNORE_ZIGBEE_DEVICES
        if CONF_COVER_SET_END_POSITION not in options:
            options[CONF_COVER_SET_END_POSITION] = DEFAULT_COVER_SET_END_POSITION
        if CONF_COVER_CLOSETIME not in options:
            options[CONF_COVER_CLOSETIME] = DEFAULT_COVER_CLOSETIME
        if CONF_COVER_USE_TIMED not in options:
            options[CONF_COVER_USE_TIMED] = DEFAULT_COVER_USE_TIMED
        if CONF_WEBSOCKET_TIMEOUT not in options:
            options[CONF_WEBSOCKET_TIMEOUT] = DEFAULT_WEBSOCKET_TIMEOUT

        self.hass.config_entries.async_update_entry(self.config_entry, options=options)

    @staticmethod
    async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
        """Handle options update."""
        # dobiss = hass.data[DOMAIN][entry.entry_id][KEY_API].api
        # websocket_timeout = entry.options.get(CONF_WEBSOCKET_TIMEOUT, DEFAULT_WEBSOCKET_TIMEOUT)
        # _LOGGER.debug(f"(update_listener) Setting websocket timeout to {websocket_timeout}")
        # if websocket_timeout == 0:
        #    dobiss.websocket_timeout = None
        # else:
        #    dobiss.websocket_timeout = websocket_timeout
        # await dobiss.update_all(force=True)

        if entry.source == SOURCE_IMPORT:
            return
        await hass.config_entries.async_reload(entry.entry_id)
