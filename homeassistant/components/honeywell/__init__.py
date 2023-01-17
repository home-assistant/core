"""Support for Honeywell (US) Total Connect Comfort climate systems."""
import asyncio
from datetime import timedelta

import AIOSomecomfort

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    _LOGGER,
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_DEV_ID,
    CONF_HEAT_AWAY_TEMPERATURE,
    CONF_LOC_ID,
    DOMAIN,
)

UPDATE_LOOP_SLEEP_TIME = 5
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

MIGRATE_OPTIONS_KEYS = {CONF_COOL_AWAY_TEMPERATURE, CONF_HEAT_AWAY_TEMPERATURE}


@callback
def _async_migrate_data_to_options(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    if not MIGRATE_OPTIONS_KEYS.intersection(config_entry.data):
        return
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            k: v for k, v in config_entry.data.items() if k not in MIGRATE_OPTIONS_KEYS
        },
        options={
            **config_entry.options,
            **{k: config_entry.data.get(k) for k in MIGRATE_OPTIONS_KEYS},
        },
    )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Honeywell thermostat."""
    _async_migrate_data_to_options(hass, config_entry)

    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    client = AIOSomecomfort.AIOSomeComfort(
        username, password, session=async_get_clientsession(hass)
    )
    try:
        await client.login()
        await client.discover()

    except AIOSomecomfort.AuthError as ex:
        # change to reauth flow in next PR that adds reauth flow.
        raise ConfigEntryNotReady(
            "Failed to initialize the Honeywell client: "
            "Check your configuration (username, password), "
            "or maybe you have exceeded the API rate limit?"
        ) from ex
    except (AIOSomecomfort.ConnectionError, AIOSomecomfort.ConnectionTimeout) as ex:
        raise ConfigEntryNotReady(
            "Failed to initialize the Honeywell client: "
            "Connection error: maybe you have exceeded the API rate limit?"
        ) from ex
    loc_id = config_entry.data.get(CONF_LOC_ID)
    dev_id = config_entry.data.get(CONF_DEV_ID)

    devices = {}
    for location in client.locations_by_id.values():
        if not loc_id or location.locationid == loc_id:
            for device in location.devices_by_id.values():
                if not dev_id or device.deviceid == dev_id:
                    devices[device.deviceid] = device

    if len(devices) == 0:
        _LOGGER.debug("No devices found")
        return False

    data = HoneywellData(hass, config_entry, client, username, password, devices)
    await data.async_update()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = data
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the config and platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok


class HoneywellData:
    """Get the latest data and update."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: AIOSomecomfort.AIOSomeComfort,
        username: str,
        password: str,
        devices: dict[str, AIOSomecomfort.device.Device],
    ) -> None:
        """Initialize the data object."""
        self._hass = hass
        self._config = config_entry
        self._client = client
        self._username = username
        self._password = password
        self.devices = devices

    async def _retry(self) -> bool:
        """Recreate a new somecomfort client.

        When we got an error, the best way to be sure that the next query
        will succeed, is to try to login.
        """
        try:
            await self._client.login()
        except AIOSomecomfort.SomeComfortError:
            return False

        refreshed_devices = [
            device
            for location in self._client.locations_by_id.values()
            for device in location.devices_by_id.values()
        ]

        if len(refreshed_devices) == 0:
            _LOGGER.error("Failed to find any devices after retry")
            return False

        for updated_device in refreshed_devices:
            if updated_device.deviceid in self.devices:
                self.devices[updated_device.deviceid] = updated_device
            else:
                _LOGGER.info(
                    "New device with ID %s detected, reload the honeywell integration"
                    " if you want to access it in Home Assistant"
                )

        await self._hass.config_entries.async_reload(self._config.entry_id)
        return True

    async def _refresh_devices(self):
        """Refresh each enabled device."""
        for device in self.devices.values():
            await device.refresh()
            await asyncio.sleep(UPDATE_LOOP_SLEEP_TIME)

    async def async_update(self) -> None:
        """Update the state."""
        retries = 3
        while retries > 0:
            try:
                await self._refresh_devices()
                break
            except (
                AIOSomecomfort.APIRateLimited,
                AIOSomecomfort.ConnectionError,
                AIOSomecomfort.ConnectionTimeout,
                OSError,
            ) as exp:
                retries -= 1
                if retries == 0:
                    _LOGGER.error(
                        "Ran out of retry attempts (3 attempts allocated). Error: %s",
                        exp,
                    )
                    raise exp

                result = await self._retry()

                if not result:
                    _LOGGER.error("Retry result was empty. Error: %s", exp)
                    raise exp

                _LOGGER.info("SomeComfort update failed, retrying. Error: %s", exp)
