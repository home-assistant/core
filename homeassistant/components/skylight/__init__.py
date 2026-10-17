"""The Skylight integration."""

from skylight_api import SkylightAPI, TokenUpdateCallback

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_FINGERPRINT, CONF_REFRESH_TOKEN, DOMAIN as DOMAIN
from .coordinator import SkylightConfigEntry, SkylightDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def _async_token_saver(
    hass: HomeAssistant, entry: SkylightConfigEntry
) -> TokenUpdateCallback:
    """Persist tokens rotated by the client's refresh cascade."""

    async def _save(
        access_token: str, refresh_token: str, device_fingerprint: str | None
    ) -> None:
        fingerprint = (
            device_fingerprint or entry.data[CONF_TOKEN][CONF_DEVICE_FINGERPRINT]
        )
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_TOKEN: {
                    CONF_ACCESS_TOKEN: access_token,
                    CONF_REFRESH_TOKEN: refresh_token,
                    CONF_DEVICE_FINGERPRINT: fingerprint,
                },
            },
        )

    return _save


async def async_setup_entry(hass: HomeAssistant, entry: SkylightConfigEntry) -> bool:
    """Set up Skylight from a config entry."""
    token = entry.data[CONF_TOKEN]
    api = SkylightAPI(
        async_get_clientsession(hass),
        access_token=token[CONF_ACCESS_TOKEN],
        refresh_token=token[CONF_REFRESH_TOKEN],
        device_fingerprint=token[CONF_DEVICE_FINGERPRINT],
        token_update_cb=await _async_token_saver(hass, entry),
    )

    coordinator = SkylightDataUpdateCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SkylightConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
