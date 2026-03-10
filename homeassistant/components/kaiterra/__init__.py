"""Support for Kaiterra devices."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigSubentry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .api_data import (
    KaiterraApiAuthError,
    KaiterraApiClient,
    KaiterraApiData,
    KaiterraApiError,
    KaiterraDeviceNotFoundError,
)
from .const import (
    AVAILABLE_AQI_STANDARDS,
    AVAILABLE_DEVICE_TYPES,
    AVAILABLE_UNITS,
    CONF_AQI_STANDARD,
    CONF_PREFERRED_UNITS,
    DEFAULT_AQI_STANDARD,
    DEFAULT_PREFERRED_UNIT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    PLATFORMS,
    SUBENTRY_TYPE_DEVICE,
)

KAITERRA_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_TYPE): vol.In(AVAILABLE_DEVICE_TYPES),
        vol.Optional(CONF_NAME): cv.string,
    }
)

KAITERRA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [KAITERRA_DEVICE_SCHEMA]),
        vol.Optional(CONF_AQI_STANDARD, default=DEFAULT_AQI_STANDARD): vol.In(
            AVAILABLE_AQI_STANDARDS
        ),
        vol.Optional(CONF_PREFERRED_UNITS, default=DEFAULT_PREFERRED_UNIT): vol.All(
            cv.ensure_list, [vol.In(AVAILABLE_UNITS)]
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: KAITERRA_SCHEMA}, extra=vol.ALLOW_EXTRA)

type KaiterraConfigEntry = ConfigEntry[KaiterraApiData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Kaiterra from YAML and import it into config entries."""
    if (conf := config.get(DOMAIN)) is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=conf,
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> bool:
    """Set up Kaiterra from a config entry."""
    await _async_validate_entry_devices(hass, entry)

    api = KaiterraApiData(
        hass,
        _entry_config(entry),
        async_get_clientsession(hass),
    )
    await api.async_update()

    entry.runtime_data = api
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    entry.async_on_unload(
        async_track_time_interval(
            hass,
            _async_update_listener(api),
            timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)),
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> None:
    """Reload the integration when the config entry or subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_validate_entry_devices(
    hass: HomeAssistant, entry: KaiterraConfigEntry
) -> None:
    """Validate auth against the first readable configured device."""
    devices = list(_iter_device_subentries(entry))
    if not devices:
        return

    validator = KaiterraApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
        entry.options.get(CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD),
    )
    saw_missing_device = False

    for subentry in devices:
        try:
            await validator.async_validate_device(
                subentry.data[CONF_TYPE],
                subentry.data[CONF_DEVICE_ID],
            )
        except KaiterraApiAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except KaiterraDeviceNotFoundError:
            saw_missing_device = True
            continue
        except KaiterraApiError as err:
            raise ConfigEntryNotReady(err) from err
        else:
            return

    if saw_missing_device:
        return


def _iter_device_subentries(entry: ConfigEntry) -> list[ConfigSubentry]:
    """Return Kaiterra device subentries for an entry."""
    return [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_DEVICE
    ]


def _entry_config(entry: ConfigEntry) -> dict[str, Any]:
    """Build the legacy runtime config from a config entry."""
    return {
        CONF_API_KEY: entry.data[CONF_API_KEY],
        CONF_DEVICES: [dict(subentry.data) for subentry in _iter_device_subentries(entry)],
        CONF_AQI_STANDARD: entry.options.get(CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD),
        CONF_PREFERRED_UNITS: entry.options.get(
            CONF_PREFERRED_UNITS, DEFAULT_PREFERRED_UNIT
        ),
    }


def _async_update_listener(api: KaiterraApiData):
    """Return the periodic update callback for an API object."""

    async def _update(now=None) -> None:
        await api.async_update()

    return _update
