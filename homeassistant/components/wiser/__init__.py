"""
Drayton Wiser Compoment for Wiser System.

Includes Climate and Sensor Devices

https://github.com/asantaga/wiserHomeAssistantPlatform
Angelo.santagata@gmail.com
"""
import asyncio
from datetime import timedelta
from functools import partial
import json

import requests.exceptions
import voluptuous as vol
from wiserHeatingAPI.wiserHub import (
    TEMP_MAXIMUM,
    TEMP_MINIMUM,
    WiserHubTimeoutException,
    wiserHub,
)

from homeassistant.const import (
    CONF_HOST,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import Throttle

from .const import (
    _LOGGER,
    CONF_BOOST_TEMP,
    CONF_BOOST_TEMP_TIME,
    DATA,
    DEFAULT_BOOST_TEMP,
    DEFAULT_BOOST_TEMP_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HUBNAME,
    MANUFACTURER,
    UPDATE_LISTENER,
    UPDATE_TRACK,
    WISER_PLATFORMS,
    WISER_SERVICES,
)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(vol.Coerce(int)),
                    vol.Optional(CONF_MINIMUM, default=TEMP_MINIMUM): vol.All(
                        vol.Coerce(int)
                    ),
                    vol.Optional(CONF_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): vol.All(
                        vol.Coerce(int)
                    ),
                    vol.Optional(
                        CONF_BOOST_TEMP_TIME, default=DEFAULT_BOOST_TEMP_TIME
                    ): vol.All(vol.Coerce(int)),
                }
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up of the Wiser Hub component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Wiser from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    _async_import_options_from_data_if_missing(hass, config_entry)

    data = WiserHubHandle(hass, config_entry,)

    try:
        await hass.async_add_executor_job(data.connect)
    except KeyError:
        _LOGGER.error("Failed to login to wiser hub")
        return False
    except RuntimeError as exc:
        _LOGGER.error("Failed to setup wiser hub: %s", exc)
        return ConfigEntryNotReady
    except requests.exceptions.HTTPError as ex:
        if ex.response.status_code > 400 and ex.response.status_code < 500:
            _LOGGER.error("Failed to login to wiser hub: %s", ex)
            return False
        raise ConfigEntryNotReady

    # Do first update
    await hass.async_add_executor_job(data.update)

    # Poll for updates in the background
    update_track = async_track_time_interval(
        hass,
        lambda now: data.update(),
        timedelta(
            seconds=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )

    update_listener = config_entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][config_entry.entry_id] = {
        DATA: data,
        UPDATE_TRACK: update_track,
        UPDATE_LISTENER: update_listener,
    }

    for platform in WISER_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    _LOGGER.info("Wiser Component Setup Completed")
    await data.async_update_device_registry()

    return True


@callback
def _async_import_options_from_data_if_missing(hass, config_entry):
    options = dict(config_entry.options)
    modified = False
    for importable_option in [
        CONF_BOOST_TEMP,
        CONF_BOOST_TEMP_TIME,
        CONF_SCAN_INTERVAL,
    ]:
        if (
            importable_option not in config_entry.options
            and importable_option in config_entry.data
        ):
            options[importable_option] = config_entry.data[importable_option]
            modified = True

    if modified:
        hass.config_entries.async_update_entry(config_entry, options=options)


async def _async_update_listener(hass, config_entry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


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
    # Unload a config entry
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in WISER_PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][config_entry.entry_id][UPDATE_TRACK]()
    hass.data[DOMAIN][config_entry.entry_id][UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class WiserHubHandle:
    """Main Wiser class handling all data."""

    def __init__(self, hass, config_entry):
        """Initialise the base class."""
        self._hass = hass
        self._config_entry = config_entry
        self._name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]
        self.secret = config_entry.data[CONF_PASSWORD]
        self.wiserhub = None
        self.minimum_temp = TEMP_MINIMUM
        self.maximum_temp = TEMP_MAXIMUM
        self.boost_temp = config_entry.options.get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP)
        self.boost_time = config_entry.options.get(
            CONF_BOOST_TEMP_TIME, DEFAULT_BOOST_TEMP_TIME
        )

    def connect(self):
        """Connect to Wiser Hub."""
        self.wiserhub = wiserHub(self.host, self.secret)
        return True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call Wiser Hub async update."""
        self._hass.async_create_task(self.async_update())

    async def async_update(self, no_throttle: bool = False):
        """Update from Wiser Hub."""
        try:
            result = await self._hass.async_add_executor_job(self.wiserhub.refreshData)
            if result is not None:
                _LOGGER.info("**Wiser Hub data updated**")
                # Send update notice to all components to update
                dispatcher_send(self._hass, "WiserHubUpdateMessage")
                return True

            _LOGGER.error("Unable to update from wiser hub")
            return False
        except json.decoder.JSONDecodeError as ex:
            _LOGGER.error(
                "Data not in JSON format when getting data from the Wiser hub. Error is %s",
                str(ex),
            )
            return False
        except WiserHubTimeoutException as ex:
            _LOGGER.error("Unable to update from Wiser hub due to timeout error")
            _LOGGER.debug("Error is %s", str(ex))
            return False
        except Exception as ex:  # pylint: disable=broad-except
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
            self.wiserhub = await self._hass.async_add_executor_job(self.connect)
        _LOGGER.debug("Setting away mode to %s with temp %s.", mode, away_temperature)
        try:
            await self._hass.async_add_executor_job(
                partial(self.wiserhub.setHomeAwayMode, mode, away_temperature)
            )
            await self.async_update(no_throttle=True)
        except BaseException as ex:  # pylint: disable=broad-except
            _LOGGER.debug("Error setting away mode! %s", str(ex))

    async def set_system_switch(self, switch, mode):
        """Set the a system switch , stored in config files."""
        if self.wiserhub is None:
            self.wiserhub = await self._hass.async_add_executor_job(self.connect)
        _LOGGER.debug("Setting %s system switch to %s.", switch, mode)
        try:
            await self._hass.async_add_executor_job(
                partial(self.wiserhub.setSystemSwitch, switch, mode)
            )
            await self.async_update(no_throttle=True)
        except BaseException as ex:  # pylint: disable=broad-except
            _LOGGER.debug("Error setting %s system switch! %s", switch, str(ex))

    async def set_smartplug_mode(self, plug_id, plug_mode):
        """
        Set the mode of the smart plug.

        :param plug_id:
        :param mode: Can be manual or auto
        :return:
        """
        if self.wiserhub is None:
            self.wiserhub = await self._hass.async_add_executor_job(self.connect)

        if plug_mode.lower() in ["auto", "manual"]:
            _LOGGER.info("Setting SmartPlug %s mode to %s ", plug_id, plug_mode)

            try:
                await self._hass.async_add_executor_job(
                    partial(self.wiserhub.setSmartPlugMode, plug_id, plug_mode)
                )
                # Add small delay to allow hub to update status before refreshing
                await asyncio.sleep(0.5)
                await self.async_update(no_throttle=True)

            except BaseException as ex:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "Error setting SmartPlug %s mode to %s, error %s",
                    plug_id,
                    plug_mode,
                    str(ex),
                )
        else:
            _LOGGER.error(
                "Plug mode can only be auto or manual. Mode was %s", plug_mode
            )

    async def set_smart_plug_state(self, plug_id, state):
        """
        Set the state of the smart plug.

        :param plug_id:
        :param state: Can be On or Off
        :return:
        """
        if self.wiserhub is None:
            self.wiserhub = await self._hass.async_add_executor_job(self.connect)
        _LOGGER.info("Setting SmartPlug %s to %s ", plug_id, state)

        try:
            await self._hass.async_add_executor_job(
                partial(self.wiserhub.setSmartPlugState, plug_id, state)
            )
            # Add small delay to allow hub to update status before refreshing
            await asyncio.sleep(0.5)
            await self.async_update(no_throttle=True)

        except BaseException as ex:  # pylint: disable=broad-except
            _LOGGER.debug(
                "Error setting SmartPlug %s to %s, error %s", plug_id, state, str(ex),
            )

    async def set_hotwater_mode(self, hotwater_mode):
        """Set the hotwater mode."""
        if self.wiserhub is None:
            self.wiserhub = await self._hass.async_add_executor_job(self.connect)
        _LOGGER.info("Setting Hotwater to %s ", hotwater_mode)
        # Add small delay to allow hub to update status before refreshing
        await asyncio.sleep(0.5)
        await self.async_update(no_throttle=True)

        try:
            await self._hass.async_add_executor_job(
                partial(self.wiserhub.setHotwaterMode, hotwater_mode)
            )
        except BaseException as ex:  # pylint: disable=broad-except
            _LOGGER.debug(
                "Error setting Hotwater Mode to  %s, error %s", hotwater_mode, str(ex),
            )
