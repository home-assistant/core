"""The Screenlogic integration."""
import asyncio
import socket
from collections import defaultdict
from datetime import timedelta

import logging

from screenlogicpy import (
    ScreenLogicGateway,
    ScreenLogicError,
    discovery,
)

from screenlogicpy.const import CONTROLLER_HARDWARE


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
)

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): cv.string,
                vol.Optional(CONF_PORT, default=80): cv.string,
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

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_IP_ADDRESS: conf[CONF_IP_ADDRESS],
                    CONF_PORT: conf[CONF_PORT],
                    CONF_SCAN_INTERVAL: conf[CONF_SCAN_INTERVAL],
                },
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Screenlogic from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    _LOGGER.info("Async Setup Entry")
    _LOGGER.info(entry.data)
    try:
        gateway = ScreenLogicGateway(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_PORT],
            name=entry.data[CONF_NAME],
        )
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
    if unload_ok:
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok


class ScreenlogicDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage the data update for the Screenlogic component."""

    def __init__(self, hass, *, config_entry, gateway):
        """Initialize the Screenlogic Data Update Coordinator"""
        self.config_entry = config_entry
        self.gateway = gateway
        self.screenlogic_data = {}
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
        return self.coordinator.gateway.name + "_" + str(self._entity_id)

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
