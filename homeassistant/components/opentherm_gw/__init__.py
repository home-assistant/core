"""Support for OpenTherm Gateway devices."""

import asyncio
import logging

import pyotgw
import pyotgw.vars as gw_vars
from serial import SerialException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CLIMATE,
    CONF_FLOOR_TEMP,
    CONF_PRECISION,
    CONF_READ_PRECISION,
    CONF_SET_PRECISION,
    CONNECTION_TIMEOUT,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    DOMAIN,
)
from .services import register_services

_LOGGER = logging.getLogger(__name__)


CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_FLOOR_TEMP, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            {
                vol.Required(CONF_DEVICE): cv.string,
                vol.Optional(CONF_CLIMATE, default={}): CLIMATE_SCHEMA,
                vol.Optional(CONF_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SENSOR]


async def options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    gateway = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][entry.data[CONF_ID]]
    async_dispatcher_send(hass, gateway.options_update_signal, entry)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the OpenTherm Gateway component."""
    if DATA_OPENTHERM_GW not in hass.data:
        hass.data[DATA_OPENTHERM_GW] = {DATA_GATEWAYS: {}}

    gateway = OpenThermGatewayHub(hass, config_entry)
    hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]] = gateway

    if config_entry.options.get(CONF_PRECISION):
        migrate_options = dict(config_entry.options)
        migrate_options.update(
            {
                CONF_READ_PRECISION: config_entry.options[CONF_PRECISION],
                CONF_SET_PRECISION: config_entry.options[CONF_PRECISION],
            }
        )
        del migrate_options[CONF_PRECISION]
        hass.config_entries.async_update_entry(config_entry, options=migrate_options)

    config_entry.add_update_listener(options_updated)

    try:
        async with asyncio.timeout(CONNECTION_TIMEOUT):
            await gateway.connect_and_subscribe()
    except (TimeoutError, ConnectionError, SerialException) as ex:
        await gateway.cleanup()
        raise ConfigEntryNotReady(
            f"Could not connect to gateway at {gateway.device_path}: {ex}"
        ) from ex

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    register_services(hass)
    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OpenTherm Gateway component."""
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        conf = config[DOMAIN]
        for device_id, device_config in conf.items():
            device_config[CONF_ID] = device_id

            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=device_config
                )
            )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Cleanup and disconnect from gateway."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    gateway = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][entry.data[CONF_ID]]
    await gateway.cleanup()
    return unload_ok


class OpenThermGatewayHub:
    """OpenTherm Gateway hub class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the OpenTherm Gateway."""
        self.hass = hass
        self.device_path = config_entry.data[CONF_DEVICE]
        self.hub_id = config_entry.data[CONF_ID]
        self.name = config_entry.data[CONF_NAME]
        self.climate_config = config_entry.options
        self.config_entry_id = config_entry.entry_id
        self.status = gw_vars.DEFAULT_STATUS
        self.update_signal = f"{DATA_OPENTHERM_GW}_{self.hub_id}_update"
        self.options_update_signal = f"{DATA_OPENTHERM_GW}_{self.hub_id}_options_update"
        self.gateway = pyotgw.OpenThermGateway()
        self.gw_version = None

    async def cleanup(self, event=None) -> None:
        """Reset overrides on the gateway."""
        await self.gateway.set_control_setpoint(0)
        await self.gateway.set_max_relative_mod("-")
        await self.gateway.disconnect()

    async def connect_and_subscribe(self) -> None:
        """Connect to serial device and subscribe report handler."""
        self.status = await self.gateway.connect(self.device_path)
        if not self.status:
            await self.cleanup()
            raise ConnectionError
        version_string = self.status[gw_vars.OTGW].get(gw_vars.OTGW_ABOUT)
        self.gw_version = version_string[18:] if version_string else None
        _LOGGER.debug(
            "Connected to OpenTherm Gateway %s at %s", self.gw_version, self.device_path
        )
        dev_reg = dr.async_get(self.hass)
        gw_dev = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry_id,
            identifiers={(DOMAIN, self.hub_id)},
            name=self.name,
            manufacturer="Schelte Bron",
            model="OpenTherm Gateway",
            sw_version=self.gw_version,
        )
        if gw_dev.sw_version != self.gw_version:
            dev_reg.async_update_device(gw_dev.id, sw_version=self.gw_version)
        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.cleanup)

        async def handle_report(status):
            """Handle reports from the OpenTherm Gateway."""
            _LOGGER.debug("Received report: %s", status)
            self.status = status
            async_dispatcher_send(self.hass, self.update_signal, status)

        self.gateway.subscribe(handle_report)

    @property
    def connected(self):
        """Report whether or not we are connected to the gateway."""
        return self.gateway.connection.connected
