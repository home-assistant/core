"""The ENGIE Belgium integration."""

from aioengiebelgium import EngieBeClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN
from .coordinator import EngieBePricesCoordinator, household_device_info

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type EngieBeConfigEntry = ConfigEntry[EngieBePricesCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> bool:
    """Set up ENGIE Belgium from a config entry."""

    async def _persist_tokens(access_token: str, refresh_token: str) -> None:
        """Persist rotated tokens to the config entry."""
        if (
            entry.data[CONF_ACCESS_TOKEN] == access_token
            and entry.data[CONF_REFRESH_TOKEN] == refresh_token
        ):
            return
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )

    client = EngieBeClient(
        session=async_get_clientsession(hass),
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        on_token_refresh=_persist_tokens,
    )

    coordinator = EngieBePricesCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    device_registry = dr.async_get(hass)
    known_agreements: set[str] = set()

    @callback
    def _async_register_devices() -> None:
        """Register a device for every business agreement not seen yet."""
        for ban, household in coordinator.data.items():
            if ban in known_agreements:
                continue
            known_agreements.add(ban)
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                **household_device_info(ban, household.agreement),
            )

    _async_register_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_register_devices))

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
