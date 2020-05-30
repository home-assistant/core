"""
Drayton Wiser Compoment for Wiser System.

Includes Climate and Sensor Devices

https://github.com/asantaga/wiserHomeAssistantPlatform
Angelo.santagata@gmail.com
"""
import asyncio
from functools import partial
import json

import voluptuous as vol
from wiserHeatingAPI.wiserHub import (
    TEMP_MAXIMUM,
    TEMP_MINIMUM,
    WiserHubTimeoutException,
    wiserHub,
)

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    _LOGGER,
    CONF_BOOST_TEMP,
    CONF_BOOST_TEMP_TIME,
    DATA_WISER_CONFIG,
    DEFAULT_BOOST_TEMP,
    DEFAULT_BOOST_TEMP_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HUBNAME,
    MANUFACTURER,
    WISER_PLATFORMS,
    WISER_SERVICES,
)

# Set config values to default
# These get set to config later
SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int)
        ),
        vol.Optional(CONF_MINIMUM, default=TEMP_MINIMUM): vol.All(vol.Coerce(int)),
        vol.Optional(CONF_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): vol.All(
            vol.Coerce(int)
        ),
        vol.Optional(CONF_BOOST_TEMP_TIME, default=DEFAULT_BOOST_TEMP_TIME): vol.All(
            vol.Coerce(int)
        ),
    }
)


async def async_setup(hass, config):
    """
    Wiser uses config flow for configuration.

    But, a "wiser:" entry in configuration.yaml will trigger an import flow
    if a config entry doesn't already exist. If it exists, the import
    flow will attempt to import it and create a config entry, to assist users
    migrating from the old wiser component. Otherwise, the user will have to
    continue setting up the integration via the config flow.
    """
    hass.data[DATA_WISER_CONFIG] = config.get(DOMAIN, {})

    if not hass.config_entries.async_entries(DOMAIN) and hass.data[DATA_WISER_CONFIG]:
        """
        No config entry exists and configuration.yaml config exists,
        so lets trigger the import flow.
        """
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=hass.data[DATA_WISER_CONFIG],
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Lets setup async service."""
    global SCAN_INTERVAL

    """Set up the Wiser component."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    SCAN_INTERVAL = int(
        config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    _LOGGER.info(
        "Wiser setup with Hub IP =  %s and scan interval of %s seconds",
        config_entry.data[CONF_HOST],
        SCAN_INTERVAL,
    )
    config_entry.add_update_listener(config_update_listener)

    data = WiserHubHandle(
        hass,
        config_entry,
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_PASSWORD],
    )

    @callback
    def retryWiserHubSetup():
        hass.async_create_task(wiserHubSetup())

    async def wiserHubSetup():
        _LOGGER.info("Initiating WiserHub connection")
        try:
            if await data.async_connect():
                if await data.async_update():
                    if data.wiserhub.getDevices is None:
                        _LOGGER.error("No Wiser devices found to set up")
                        return False

                    hass.data[DOMAIN] = data

                    for platform in WISER_PLATFORMS:
                        hass.async_create_task(
                            hass.config_entries.async_forward_entry_setup(
                                config_entry, platform
                            )
                        )

                    _LOGGER.info("Wiser Component Setup Completed")
                    await data.async_update_device_registry()
                    return True
                else:
                    await scheduleWiserHubSetup()
                    return True
        except (asyncio.TimeoutError):
            await scheduleWiserHubSetup()
            return True
        except WiserHubTimeoutException:
            await scheduleWiserHubSetup()
            return True
        except Exception:
            await scheduleWiserHubSetup()
            return True

    async def scheduleWiserHubSetup(interval=10):
        _LOGGER.error(
            "Unable to connect to the Wiser Hub, retrying in %s seconds", interval,
        )
        hass.loop.call_later(interval, retryWiserHubSetup)
        return

    await wiserHubSetup()
    return True


async def async_unload_entry(hass, config_entry):
    """
    Unload a config entry.

    :param hass:
    :param config_entry:
    :return:
    """
    # Deregister services
    _LOGGER.debug("Unregister Wiser Services")
    for service in WISER_SERVICES:
        hass.services.async_remove(DOMAIN, WISER_SERVICES[service])

    _LOGGER.debug("Unloading Wiser Component")
    tasks = []
    for platform in WISER_PLATFORMS:
        tasks.append(
            hass.config_entries.async_forward_entry_unload(config_entry, platform)
        )

    unload_status = all(await asyncio.gather(*tasks))
    if unload_status:
        hass.data.pop(DOMAIN)
    return unload_status


async def config_update_listener(hass, config_entry):
    """Handle config update update."""
    global SCAN_INTERVAL

    SCAN_INTERVAL = int(config_entry.data.get(CONF_SCAN_INTERVAL))
    _LOGGER.info(
        "Wiser config parameters changed. Boost temp = %s, Boost time = %s, "
        + "scan interval = %s",
        config_entry.data[CONF_BOOST_TEMP],
        config_entry.data[CONF_BOOST_TEMP_TIME],
        SCAN_INTERVAL,
    )


class WiserHubHandle:
    """Main Wiser class handling all data."""

    def __init__(self, hass, config_entry, ip, secret):
        """Initialise the base class."""
        self._hass = hass
        self._config_entry = config_entry
        self._name = config_entry.data[CONF_NAME]
        self.ip = ip
        self.secret = secret
        self.wiserhub = None
        self.minimum_temp = TEMP_MINIMUM
        self.maximum_temp = TEMP_MAXIMUM
        self.boost_temp = config_entry.data.get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP)
        self.boost_time = config_entry.data.get(
            CONF_BOOST_TEMP_TIME, DEFAULT_BOOST_TEMP_TIME
        )
        self.timer_handle = None

    async def async_connect(self):
        """Manage the async connection request."""
        self.wiserhub = await self._hass.async_add_executor_job(
            partial(wiserHub, self.ip, self.secret)
        )
        return True

    @callback
    def do_hub_update(self):
        """Lets update the hub."""
        self._hass.async_create_task(self.async_update())

    async def async_update(self, no_throttle: bool = False):
        """Update uses event loop scheduler for scan interval."""
        if no_throttle:
            # Forced update
            _LOGGER.info("Update of Wiser Hub data requested via On Demand")
            # Cancel next scheduled update and schedule for next interval
            if self.timer_handle:
                self.timer_handle.cancel()
        else:
            # Updated on schedule
            _LOGGER.info(
                "Update of Wiser Hub data requested on %s seconds interval",
                SCAN_INTERVAL,
            )
        # Schedule next update
        self.timer_handle = self._hass.loop.call_later(
            SCAN_INTERVAL, self.do_hub_update
        )

        try:
            # Update from hub
            result = await self._hass.async_add_executor_job(self.wiserhub.refreshData)
            if result is not None:
                _LOGGER.info("**Wiser Hub data updated**")
                # Send update notice to all components to update
                dispatcher_send(self._hass, "WiserHubUpdateMessage")
                return True
            else:
                _LOGGER.error("Unable to update from wiser hub")
                return False
        except json.decoder.JSONDecodeError as JSONex:
            _LOGGER.error(
                "Data not in JSON format when getting data from the Wiser hub,"
                + "did you enter the right URL? error %s",
                str(JSONex),
            )
            return False
        except WiserHubTimeoutException as ex:
            _LOGGER.error("Unable to update from Wiser hub due to timeout error")
            _LOGGER.debug("Error is %s", str(ex))
            return False
        except Exception as ex:
            _LOGGER.error("Unable to update from Wiser hub due to unknown error")
            _LOGGER.debug("Error is %s", str(ex))
            return False

    @property
    def unique_id(self):
        """Return a unique name, otherwise config flow does not work right."""
        return self._name

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = await self._hass.helpers.device_registry.async_get_registry()
        device_registry.async_get_or_create(
            config_entry_id=self._config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.wiserhub.getMACAddress())},
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer=MANUFACTURER,
            name=HUBNAME,
            model=self.wiserhub.getDevice(0).get("ProductType"),
            sw_version=self.wiserhub.getDevice(0).get("ActiveFirmwareVersion"),
        )

    async def set_away_mode(self, away, away_temperature):
        """Set Away mode, with temp."""
        mode = "AWAY" if away else "HOME"
        if self.wiserhub is None:
            self.wiserhub = await self.async_connect()
        _LOGGER.debug("Setting away mode to %s with temp %s.", mode, away_temperature)
        try:
            await self._hass.async_add_executor_job(
                partial(self.wiserhub.setHomeAwayMode, mode, away_temperature)
            )
            await self.async_update(no_throttle=True)
        except BaseException as e:
            _LOGGER.debug("Error setting away mode! %s", str(e))

    async def set_system_switch(self, switch, mode):
        """Set the a system switch , stored in config files."""
        if self.wiserhub is None:
            self.wiserhub = await self.async_connect()
        _LOGGER.debug("Setting %s system switch to %s.", switch, mode)
        try:
            await self._hass.async_add_executor_job(
                partial(self.wiserhub.setSystemSwitch, switch, mode)
            )
            await self.async_update(no_throttle=True)
        except BaseException as e:
            _LOGGER.debug("Error setting %s system switch! %s", switch, str(e))

    async def set_smart_plug_state(self, plug_id, state):
        """
        Set the state of the smart plug.

        :param plug_id:
        :param state: Can be On or Off
        :return:
        """
        if self.wiserhub is None:
            self.wiserhub = await self.async_connect()
        _LOGGER.info("Setting SmartPlug %s to %s ", plug_id, state)

        try:
            await self._hass.async_add_executor_job(
                partial(self.wiserhub.setSmartPlugState, plug_id, state)
            )
            # Add small delay to allow hub to update status before refreshing
            await asyncio.sleep(0.5)
            await self.async_update(no_throttle=True)

        except BaseException as e:
            _LOGGER.debug(
                "Error setting SmartPlug %s to %s, error %s", plug_id, state, str(e),
            )

    async def set_hotwater_mode(self, hotwater_mode):
        """Set the hotwater mode."""
        if self.wiserhub is None:
            self.wiserhub = await self.async_connect()
        _LOGGER.info("Setting Hotwater to %s ", hotwater_mode)
        # Add small delay to allow hub to update status before refreshing
        await asyncio.sleep(0.5)
        await self.async_update(no_throttle=True)

        try:
            await self._hass.async_add_executor_job(
                partial(self.wiserhub.setHotwaterMode, hotwater_mode)
            )
        except BaseException as e:
            _LOGGER.debug(
                "Error setting Hotwater Mode to  %s, error %s".hotwater_mode, str(e),
            )
