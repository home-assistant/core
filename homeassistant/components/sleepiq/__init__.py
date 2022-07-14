"""Support for SleepIQ from SleepNumber."""
from __future__ import annotations

import logging
from typing import Any

from asyncsleepiq import (
    AsyncSleepIQ,
    SleepIQAPIException,
    SleepIQLoginException,
    SleepIQTimeoutException,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, PRESSURE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, IS_IN_BED, SLEEP_NUMBER
from .coordinator import (
    SleepIQData,
    SleepIQDataUpdateCoordinator,
    SleepIQPauseUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up sleepiq component."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SleepIQ config entry."""
    conf = entry.data
    email = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    client_session = async_get_clientsession(hass)

    gateway = AsyncSleepIQ(client_session=client_session)

    try:
        await gateway.login(email, password)
    except SleepIQLoginException as err:
        _LOGGER.error("Could not authenticate with SleepIQ server")
        raise ConfigEntryAuthFailed(err) from err
    except SleepIQTimeoutException as err:
        raise ConfigEntryNotReady(
            str(err) or "Timed out during authentication"
        ) from err

    try:
        await gateway.init_beds()
    except SleepIQTimeoutException as err:
        raise ConfigEntryNotReady(
            str(err) or "Timed out during initialization"
        ) from err
    except SleepIQAPIException as err:
        raise ConfigEntryNotReady(str(err) or "Error reading from SleepIQ API") from err

    await _async_migrate_unique_ids(hass, entry, gateway)

    coordinator = SleepIQDataUpdateCoordinator(hass, gateway, email)
    pause_coordinator = SleepIQPauseUpdateCoordinator(hass, gateway, email)

    # Call the SleepIQ API to refresh data
    await coordinator.async_config_entry_first_refresh()
    await pause_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = SleepIQData(
        data_coordinator=coordinator,
        pause_coordinator=pause_coordinator,
        client=gateway,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, gateway: AsyncSleepIQ
) -> None:
    """Migrate old unique ids."""
    names_to_ids = {
        sleeper.name: sleeper.sleeper_id
        for bed in gateway.beds.values()
        for sleeper in bed.sleepers
    }

    bed_ids = {bed.id for bed in gateway.beds.values()}

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        # Old format for sleeper entities was {bed_id}_{sleeper.name}_{sensor_type}.....
        # New format is {sleeper.sleeper_id}_{sensor_type}....
        sensor_types = [IS_IN_BED, PRESSURE, SLEEP_NUMBER]

        old_unique_id = entity_entry.unique_id
        parts = old_unique_id.split("_")

        # If it doesn't begin with a bed id or end with one of the sensor types,
        # it doesn't need to be migrated
        if parts[0] not in bed_ids or not old_unique_id.endswith(tuple(sensor_types)):
            return None

        sensor_type = next(filter(old_unique_id.endswith, sensor_types))
        sleeper_name = "_".join(parts[1:]).removesuffix(f"_{sensor_type}")
        sleeper_id = names_to_ids.get(sleeper_name)

        if not sleeper_id:
            return None

        new_unique_id = f"{sleeper_id}_{sensor_type}"

        _LOGGER.debug(
            "Migrating unique_id from [%s] to [%s]",
            old_unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await er.async_migrate_entries(hass, entry.entry_id, _async_migrator)
