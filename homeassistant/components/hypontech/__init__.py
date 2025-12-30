"""The Hypontech Cloud integration."""

from __future__ import annotations

from hyponcloud import AuthenticationError, HyponCloud

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import HypontechData, HypontechDataCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type HypontechConfigEntry = ConfigEntry[HypontechData]


async def async_setup_entry(hass: HomeAssistant, entry: HypontechConfigEntry) -> bool:
    """Set up Hypontech Cloud from a config entry."""
    session = async_get_clientsession(hass)
    hypontech_cloud = HyponCloud(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
    )
    try:
        await hypontech_cloud.connect()
    except AuthenticationError as ex:
        raise ConfigEntryAuthFailed("Authentication failed for Hypontech Cloud") from ex
    except (TimeoutError, ConnectionError) as ex:
        raise ConfigEntryNotReady("Cannot connect to Hypontech Cloud") from ex

    coordinator = HypontechDataCoordinator(hass, entry, hypontech_cloud)
    await coordinator.async_config_entry_first_refresh()

    # Create device. One account can have multiple devices. But for now, we only support
    # one "Overview" device.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Hypontech",
        model="Overview",
    )

    entry.runtime_data = HypontechData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HypontechConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
