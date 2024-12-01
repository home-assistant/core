"""Support for Honeywell (US) Total Connect Comfort climate systems."""

from dataclasses import dataclass

from aiohttp.client_exceptions import ClientConnectionError
import aiosomecomfort

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)

from .const import (
    _LOGGER,
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
)

UPDATE_LOOP_SLEEP_TIME = 5
PLATFORMS = [Platform.CLIMATE, Platform.HUMIDIFIER, Platform.SENSOR, Platform.SWITCH]

MIGRATE_OPTIONS_KEYS = {CONF_COOL_AWAY_TEMPERATURE, CONF_HEAT_AWAY_TEMPERATURE}

type HoneywellConfigEntry = ConfigEntry[HoneywellData]


@callback
def _async_migrate_data_to_options(
    hass: HomeAssistant, config_entry: HoneywellConfigEntry
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


async def async_setup_entry(
    hass: HomeAssistant, config_entry: HoneywellConfigEntry
) -> bool:
    """Set up the Honeywell thermostat."""
    _async_migrate_data_to_options(hass, config_entry)

    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    if len(hass.config_entries.async_entries(DOMAIN)) > 1:
        session = async_create_clientsession(hass)
    else:
        session = async_get_clientsession(hass)

    client = aiosomecomfort.AIOSomeComfort(username, password, session=session)
    try:
        await client.login()
        await client.discover()

    except aiosomecomfort.device.AuthError as ex:
        raise ConfigEntryAuthFailed("Incorrect Password") from ex

    except (
        aiosomecomfort.device.ConnectionError,
        aiosomecomfort.device.ConnectionTimeout,
        aiosomecomfort.device.SomeComfortError,
        ClientConnectionError,
        TimeoutError,
    ) as ex:
        raise ConfigEntryNotReady(
            "Failed to initialize the Honeywell client: Connection error"
        ) from ex

    devices = {}
    for location in client.locations_by_id.values():
        for device in location.devices_by_id.values():
            devices[device.deviceid] = device

    if len(devices) == 0:
        _LOGGER.debug("No devices found")
        return False
    config_entry.runtime_data = HoneywellData(config_entry.entry_id, client, devices)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    return True


async def update_listener(
    hass: HomeAssistant, config_entry: HoneywellConfigEntry
) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: HoneywellConfigEntry
) -> bool:
    """Unload the config and platforms."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


@dataclass
class HoneywellData:
    """Shared data for Honeywell."""

    entry_id: str
    client: aiosomecomfort.AIOSomeComfort
    devices: dict[str, aiosomecomfort.device.Device]
