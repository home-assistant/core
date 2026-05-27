"""The ALLNET integration."""

from __future__ import annotations

from dataclasses import dataclass

from allnet import AllnetClient, AllnetConnectionError
from allnet.exceptions import AllnetAuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_DEVICE_PROFILE, CONF_USE_SSL, DEFAULT_USE_SSL, DOMAIN
from .coordinator import AllnetDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

type AllnetConfigEntry = ConfigEntry[AllnetRuntimeData]


@dataclass
class AllnetRuntimeData:
    """Runtime data stored on the config entry."""

    client: AllnetClient
    coordinator: AllnetDataUpdateCoordinator
    ha_device_info: DeviceInfo


async def async_setup_entry(hass: HomeAssistant, entry: AllnetConfigEntry) -> bool:
    """Set up ALLNET from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME) or None
    password = entry.data.get(CONF_PASSWORD) or None
    use_ssl = entry.data.get(CONF_USE_SSL, DEFAULT_USE_SSL)

    session = async_get_clientsession(hass)
    client = AllnetClient(
        host=host,
        username=username,
        password=password,
        use_ssl=use_ssl,
        session=session,
    )

    try:
        device_info = await client.async_get_device_info()
    except AllnetAuthenticationError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed for {host}: {err}") from err
    except AllnetConnectionError as err:
        raise ConfigEntryNotReady(f"Cannot connect to {host}: {err}") from err

    coordinator = AllnetDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    configuration_url = f"{'https' if use_ssl else 'http'}://{host}"
    connections: set[tuple[str, str]] = set()
    if device_info.mac_address:
        from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
        connections = {(CONNECTION_NETWORK_MAC, device_info.mac_address)}

    ha_device_info = DeviceInfo(
        identifiers={(DOMAIN, device_info.unique_id)},
        connections=connections,
        manufacturer="ALLNET",
        model=device_info.model,
        name=device_info.name or device_info.model or "ALLNET",
        sw_version=device_info.sw_version,
        hw_version=device_info.hw_version,
        configuration_url=configuration_url,
    )

    entry.runtime_data = AllnetRuntimeData(
        client=client,
        coordinator=coordinator,
        ha_device_info=ha_device_info,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AllnetConfigEntry) -> bool:
    """Unload an ALLNET config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
