"""The Screenlogic integration."""
import asyncio
import socket
from slugify import slugify
from collections import defaultdict
from datetime import timedelta

import logging

from screenlogicpy import (
    ScreenLogicGateway,
    ScreenLogicError,
    discovery,
)

from screenlogicpy.const import (
    CONTROLLER_HARDWARE,
    SL_GATEWAY_IP,
    SL_GATEWAY_PORT,
    SL_GATEWAY_TYPE,
    SL_GATEWAY_SUBTYPE,
    SL_GATEWAY_NAME,
)

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)


from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_NAME,
    CONF_HOST,
    CONF_DISCOVERY,
)

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

from .config_flow import discover_gateways

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): cv.string,
                vol.Optional(CONF_PORT, default=80): cv.positive_int,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["switch", "sensor", "binary_sensor", "water_heater"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Screenlogic component."""
    _LOGGER.info("Async Setup")
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        _LOGGER.info("conf found")
        _LOGGER.info(conf)
        if CONF_NAME not in conf:
            conf[CONF_NAME] = "Unnamed ScreenLogic"
        config_data = {
            CONF_HOST: {
                CONF_IP_ADDRESS: conf[CONF_IP_ADDRESS],
                CONF_PORT: conf[CONF_PORT],
                CONF_NAME: conf[CONF_NAME],
            },
        }
        if CONF_SCAN_INTERVAL in conf:
            config_data[CONF_SCAN_INTERVAL] = conf[CONF_SCAN_INTERVAL]

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=config_data,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Screenlogic from a config entry."""

    _LOGGER.debug("Async Setup Entry")
    _LOGGER.debug(entry.data)

    if CONF_HOST not in entry.data:
        _LOGGER.error("Invalid config_entry: Missing CONF_HOST")
        return False

    connect_info = {}
    if CONF_NAME in entry.data[CONF_HOST]:
        # Attempt to re-discover named gateway to follow IP changes
        hosts = await hass.async_add_executor_job(discover_gateways)
        if len(hosts) > 0:
            for host in hosts:
                if host[SL_GATEWAY_NAME] == entry.data[CONF_HOST][CONF_NAME]:
                    connect_info = host
                    break
            if not connect_info:
                _LOGGER.warning("Gateway name matching failed.")

    if not connect_info and CONF_IP_ADDRESS in entry.data[CONF_HOST]:
        # Static connection defined or fallback from discovery
        connect_info[SL_GATEWAY_NAME] = (
            entry.data[CONF_HOST][CONF_NAME]
            if CONF_NAME in entry.data[CONF_HOST]
            else "ScreenLogic"
        )
        connect_info[SL_GATEWAY_IP] = entry.data[CONF_HOST][CONF_IP_ADDRESS]
        if CONF_PORT in entry.data[CONF_HOST]:
            connect_info[SL_GATEWAY_PORT] = entry.data[CONF_HOST][CONF_PORT]

    if not connect_info:
        _LOGGER.error("Invalid config_entry")
        return False

    try:
        gateway = ScreenLogicGateway(**connect_info)
    except ScreenLogicError as error:
        _LOGGER.error(error)
        return False

    coordinator = ScreenlogicDataUpdateCoordinator(
        hass, config_entry=entry, gateway=gateway
    )

    entities = defaultdict(list)

    await coordinator.async_refresh()

    for circuit in coordinator.data["circuits"]:
        entities["switch"].append(circuit)

    for sensor in coordinator.data["sensors"]:
        if sensor == "chem_alarm":
            entities["binary_sensor"].append(sensor)
        else:
            if coordinator.data["sensors"][sensor]["value"] != 0:
                entities["sensor"].append(sensor)

    for pump in coordinator.data["pumps"]:
        if (
            coordinator.data["pumps"][pump]["data"] != 0
            and "currentWatts" in coordinator.data["pumps"][pump]
        ):
            entities["pump"].append(pump)

    for body in coordinator.data["bodies"]:
        entities["water_heater"].append(body)

    hass.data[DOMAIN][entry.unique_id] = {
        "coordinator": coordinator,
        "devices": entities,
        "listener": entry.add_update_listener(async_update_listener),
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.info("Async Unload Entry")
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    hass.data[DOMAIN][entry.unique_id]["listener"]()
    if unload_ok:
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update"""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.unique_id][
        "coordinator"
    ]
    new_interval = entry.options.get(CONF_SCAN_INTERVAL)
    coordinator.update_interval = timedelta(seconds=new_interval)
    hass.config_entries.async_reload(entry.entry_id)
    _LOGGER.debug("Update interval set to {}".format(new_interval))


class ScreenlogicDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage the data update for the Screenlogic component."""

    def __init__(self, hass, *, config_entry, gateway):
        """Initialize the Screenlogic Data Update Coordinator"""
        self.config_entry = config_entry
        self.gateway = gateway
        self.screenlogic_data = {}
        interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
        if CONF_SCAN_INTERVAL in config_entry.options:
            interval = timedelta(seconds=config_entry.options[CONF_SCAN_INTERVAL])
        elif CONF_SCAN_INTERVAL in config_entry.data:
            interval = timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL])
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
        )

    async def _async_update_data(self):
        """Fetch data from the Screenlogic gateway."""
        try:
            self.gateway.update()
            return self.gateway.get_data()
        except ScreenLogicError as error:
            raise UpdateFailed(error) from error


class ScreenlogicEntity(CoordinatorEntity):
    """Base class for all ScreenLogic entities"""

    def __init__(self, coordinator, datakey):
        """Initialize of the sensor."""
        super().__init__(coordinator)
        self._entity_id = datakey

    @property
    def unique_id(self):
        slugged_name = slugify(self.coordinator.gateway.name)
        return slugged_name + "_" + str(self._entity_id)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.gateway.name)},
            "name": self.coordinator.gateway.name,
            "manufacturer": "Pentair",
            "model": CONTROLLER_HARDWARE[
                self.coordinator.data["config"]["controler_type"]
            ][self.coordinator.data["config"]["hardware_type"]],
        }
