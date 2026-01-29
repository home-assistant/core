"""The Teltonika integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from teltasync import Teltasync, TeltonikaAuthenticationError, TeltonikaConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_VALIDATE_SSL, DOMAIN
from .coordinator import TeltonikaDataUpdateCoordinator
from .util import normalize_url

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type TeltonikaConfigEntry = ConfigEntry[TeltonikaData]


@dataclass
class TeltonikaData:
    """Runtime data for Teltonika integration."""

    coordinator: TeltonikaDataUpdateCoordinator
    device_info: DeviceInfo


async def async_setup_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Set up Teltonika from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    validate_ssl = entry.data.get(CONF_VALIDATE_SSL, False)
    session = async_get_clientsession(hass)

    base_url = normalize_url(host)

    client = Teltasync(
        base_url=f"{base_url}/api",
        username=username,
        password=password,
        session=session,
        verify_ssl=validate_ssl,
    )

    try:
        await client.get_device_info()
        system_info_response = await client.get_system_info()
    except TeltonikaAuthenticationError as err:
        await client.close()
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except TeltonikaConnectionError as err:
        await client.close()
        raise ConfigEntryNotReady(f"Failed to connect to device: {err}") from err

    # Create device info for device registry
    device_info = DeviceInfo(
        identifiers={(DOMAIN, system_info_response.mnf_info.serial)},
        name=system_info_response.static.device_name,
        manufacturer="Teltonika",
        model=system_info_response.static.model,
        sw_version=system_info_response.static.fw_version,
        serial_number=system_info_response.mnf_info.serial,
        configuration_url=base_url,
    )

    # Create coordinator
    coordinator = TeltonikaDataUpdateCoordinator(hass, client, entry)

    # Fetch initial data to ensure device is reachable
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = TeltonikaData(coordinator, device_info)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.coordinator.client.close()

    return unload_ok
