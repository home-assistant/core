"""The pi_hole component."""
from __future__ import annotations

import logging

from hole import Hole
from hole.exceptions import HoleError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_LOCATION,
    CONF_STATISTICS_ONLY,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DEFAULT_LOCATION,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)

_LOGGER = logging.getLogger(__name__)

PI_HOLE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_API_KEY): cv.string,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_LOCATION, default=DEFAULT_LOCATION): cv.string,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [PI_HOLE_SCHEMA]))},
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Pi-hole integration."""

    hass.data[DOMAIN] = {}

    # import
    if DOMAIN in config:
        for conf in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pi-hole entry."""
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    use_tls = entry.data[CONF_SSL]
    verify_tls = entry.data[CONF_VERIFY_SSL]
    location = entry.data[CONF_LOCATION]
    api_key = entry.data.get(CONF_API_KEY)

    # For backward compatibility
    if CONF_STATISTICS_ONLY not in entry.data:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_STATISTICS_ONLY: not api_key}
        )

    _LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

    try:
        session = async_get_clientsession(hass, verify_tls)
        api = Hole(
            host,
            hass.loop,
            session,
            location=location,
            tls=use_tls,
            api_token=api_key,
        )
        await api.get_data()
    except HoleError as ex:
        _LOGGER.warning("Failed to connect: %s", ex)
        raise ConfigEntryNotReady from ex

    async def async_update_data() -> None:
        """Fetch data from API endpoint."""
        try:
            await api.get_data()
        except HoleError as err:
            raise UpdateFailed(f"Failed to communicate with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api,
        DATA_KEY_COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, _async_platforms(entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Pi-hole entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, _async_platforms(entry)
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


@callback
def _async_platforms(entry: ConfigEntry) -> list[str]:
    """Return platforms to be loaded / unloaded."""
    platforms = ["sensor"]
    if not entry.data[CONF_STATISTICS_ONLY]:
        platforms.append("switch")
    else:
        platforms.append("binary_sensor")
    return platforms


class PiHoleEntity(CoordinatorEntity):
    """Representation of a Pi-hole entity."""

    def __init__(
        self,
        api: Hole,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
    ) -> None:
        """Initialize a Pi-hole entity."""
        super().__init__(coordinator)
        self.api = api
        self._name = name
        self._server_unique_id = server_unique_id

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return "mdi:pi-hole"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""
        return {
            "identifiers": {(DOMAIN, self._server_unique_id)},
            "name": self._name,
            "manufacturer": "Pi-hole",
        }
