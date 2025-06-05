"""Support for OpenTherm Gateway devices."""

import asyncio
import logging

from pyotgw import OpenThermGateway
import pyotgw.vars as gw_vars
from serial import SerialException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_TEMPORARY_OVRD_MODE,
    CONNECTION_TIMEOUT,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    DOMAIN,
    OpenThermDataSource,
    OpenThermDeviceIdentifier,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up OpenTherm Gateway integration."""

    async_setup_services(hass)

    return True


async def options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    gateway = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][entry.data[CONF_ID]]
    gateway.options = entry.options
    async_dispatcher_send(hass, gateway.options_update_signal, entry)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the OpenTherm Gateway component."""
    if DATA_OPENTHERM_GW not in hass.data:
        hass.data[DATA_OPENTHERM_GW] = {DATA_GATEWAYS: {}}

    gateway = OpenThermGatewayHub(hass, config_entry)
    hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]] = gateway

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
        self.options = config_entry.options
        self.config_entry_id = config_entry.entry_id
        self.update_signal = f"{DATA_OPENTHERM_GW}_{self.hub_id}_update"
        self.options_update_signal = f"{DATA_OPENTHERM_GW}_{self.hub_id}_options_update"
        self.gateway = OpenThermGateway()
        self.gw_version = None

    async def cleanup(self, event=None) -> None:
        """Reset overrides on the gateway."""
        await self.gateway.set_control_setpoint(0)
        await self.gateway.set_max_relative_mod("-")
        await self.gateway.disconnect()

    async def connect_and_subscribe(self) -> None:
        """Connect to serial device and subscribe report handler."""
        status = await self.gateway.connect(self.device_path)
        if not status:
            await self.cleanup()
            raise ConnectionError
        version_string = status[OpenThermDataSource.GATEWAY].get(gw_vars.OTGW_ABOUT)
        self.gw_version = version_string[18:] if version_string else None
        _LOGGER.debug(
            "Connected to OpenTherm Gateway %s at %s", self.gw_version, self.device_path
        )
        dev_reg = dr.async_get(self.hass)
        gw_dev = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry_id,
            identifiers={
                (DOMAIN, f"{self.hub_id}-{OpenThermDeviceIdentifier.GATEWAY}")
            },
            manufacturer="Schelte Bron",
            model="OpenTherm Gateway",
            translation_key="gateway_device",
            sw_version=self.gw_version,
        )
        if gw_dev.sw_version != self.gw_version:
            dev_reg.async_update_device(gw_dev.id, sw_version=self.gw_version)

        boiler_device = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry_id,
            identifiers={(DOMAIN, f"{self.hub_id}-{OpenThermDeviceIdentifier.BOILER}")},
            translation_key="boiler_device",
        )
        thermostat_device = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry_id,
            identifiers={
                (DOMAIN, f"{self.hub_id}-{OpenThermDeviceIdentifier.THERMOSTAT}")
            },
            translation_key="thermostat_device",
        )

        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.cleanup)

        async def handle_report(status):
            """Handle reports from the OpenTherm Gateway."""
            _LOGGER.debug("Received report: %s", status)
            async_dispatcher_send(self.hass, self.update_signal, status)

            dev_reg.async_update_device(
                boiler_device.id,
                manufacturer=status[OpenThermDataSource.BOILER].get(
                    gw_vars.DATA_SLAVE_MEMBERID
                ),
                model_id=status[OpenThermDataSource.BOILER].get(
                    gw_vars.DATA_SLAVE_PRODUCT_TYPE
                ),
                hw_version=status[OpenThermDataSource.BOILER].get(
                    gw_vars.DATA_SLAVE_PRODUCT_VERSION
                ),
                sw_version=status[OpenThermDataSource.BOILER].get(
                    gw_vars.DATA_SLAVE_OT_VERSION
                ),
            )

            dev_reg.async_update_device(
                thermostat_device.id,
                manufacturer=status[OpenThermDataSource.THERMOSTAT].get(
                    gw_vars.DATA_MASTER_MEMBERID
                ),
                model_id=status[OpenThermDataSource.THERMOSTAT].get(
                    gw_vars.DATA_MASTER_PRODUCT_TYPE
                ),
                hw_version=status[OpenThermDataSource.THERMOSTAT].get(
                    gw_vars.DATA_MASTER_PRODUCT_VERSION
                ),
                sw_version=status[OpenThermDataSource.THERMOSTAT].get(
                    gw_vars.DATA_MASTER_OT_VERSION
                ),
            )

        self.gateway.subscribe(handle_report)

    @property
    def connected(self):
        """Report whether or not we are connected to the gateway."""
        return self.gateway.connection.connected

    async def set_room_setpoint(self, temp) -> float:
        """Set the room temperature setpoint on the gateway. Return the new temperature."""
        return await self.gateway.set_target_temp(
            temp, self.options.get(CONF_TEMPORARY_OVRD_MODE, True)
        )
