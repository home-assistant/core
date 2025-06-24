"""Dreo for Integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from pydreo.client import DreoClient
from pydreo.exceptions import DreoBusinessException, DreoException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .coordinator import DreoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type DreoConfigEntry = ConfigEntry[DreoData]

PLATFORMS = [Platform.FAN]


@dataclass
class DreoData:
    """Dreo Data."""

    client: DreoClient
    devices: list[dict[str, Any]]
    coordinators: dict[str, DreoDataUpdateCoordinator]


async def async_login(
    hass: HomeAssistant, username: str, password: str
) -> tuple[DreoClient, list[dict[str, Any]]]:
    """Log into Dreo and return client and device data."""
    client = DreoClient(username, password)

    def setup_client():
        client.login()
        return client.get_devices()

    try:
        devices = await hass.async_add_executor_job(setup_client)
    except DreoBusinessException as ex:
        raise ConfigEntryAuthFailed("Invalid username or password") from ex
    except DreoException as ex:
        raise ConfigEntryNotReady(f"Error communicating with Dreo API: {ex}") from ex

    return client, devices


async def async_setup_entry(hass: HomeAssistant, config_entry: DreoConfigEntry) -> bool:
    """Set up Dreo from as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    client, devices = await async_login(hass, username, password)
    coordinators: dict[str, DreoDataUpdateCoordinator] = {}

    for device in devices:
        await async_setup_device_coordinator(hass, client, device, coordinators)

    config_entry.runtime_data = DreoData(client, devices, coordinators)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_setup_device_coordinator(
    hass: HomeAssistant,
    client: DreoClient,
    device: dict[str, Any],
    coordinators: dict[str, DreoDataUpdateCoordinator],
) -> None:
    """Set up coordinator for a single device."""

    device_model = device.get("model")
    device_id = device.get("deviceSn")
    device_type = device.get("deviceType")
    model_config = device.get("config")

    if not device_id or not device_model or not device_type:
        return

    if model_config is None:
        _LOGGER.warning("Model config is not available for model %s", device_model)
        return

    if device_id in coordinators:
        return

    coordinator = DreoDataUpdateCoordinator(
        hass, client, device_id, device_type, model_config
    )

    if coordinator.data_processor is None:
        return

    await coordinator.async_config_entry_first_refresh()
    coordinators[device_id] = coordinator


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
