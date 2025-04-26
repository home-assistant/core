"""Dreo for Integration."""

from dataclasses import dataclass
from typing import Any

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import DreoDataUpdateCoordinator

type DreoConfigEntry = ConfigEntry[DreoData]

PLATFORMS = [Platform.FAN]


@dataclass
class DreoData:
    """Dreo Data."""

    client: HsCloud
    devices: list[dict[str, Any]]
    coordinators: dict[str, DreoDataUpdateCoordinator]


async def async_login(hass: HomeAssistant, username: str, password: str) -> DreoData:
    """Log into Dreo and return client and device data."""
    client = HsCloud(username, password)

    def setup_client():
        client.login()
        return client.get_devices()

    try:
        devices = await hass.async_add_executor_job(setup_client)
    except HsCloudException as ex:
        raise ConfigEntryNotReady("unable to connect") from ex
    except HsCloudBusinessException as ex:
        raise ConfigEntryNotReady("invalid username or password") from ex

    return DreoData(client, devices, {})


async def async_setup_entry(hass: HomeAssistant, config_entry: DreoConfigEntry) -> bool:
    """Set up Dreo from as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    # Login and get device data
    config_entry.runtime_data = await async_login(hass, username, password)

    # Create coordinators for each device
    for device in config_entry.runtime_data.devices:
        device_model = device.get("model")
        device_id = str(device.get("deviceSn", ""))

        if not device_id:
            continue

        # Create coordinator for this device
        coordinator = DreoDataUpdateCoordinator(
            hass, config_entry.runtime_data.client, device_id, device_model or ""
        )

        # Fetch initial data
        await coordinator.async_config_entry_first_refresh()

        # Store coordinator in runtime_data
        config_entry.runtime_data.coordinators[device_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
