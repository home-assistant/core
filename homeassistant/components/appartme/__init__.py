"""Appartme Integration."""

from datetime import timedelta
import json
import logging
import os

from appartme_paas import AppartmePaasClient

from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_URL, DOMAIN, UPDATE_INTERVAL_DEFAULT
from .coordinator import AppartmeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
]


def read_translation_file(translation_file: str) -> dict:
    """Read the translation file synchronously."""
    with open(translation_file, encoding="utf8") as file:
        return json.load(file)


def get_logbook_translation(
    translations: dict, translation_key: str, default_name=None, **kwargs
) -> str:
    """Fetch the translated logbook entry with formatting."""
    translation_template = translations.get("logbook", {}).get(
        translation_key, default_name or translation_key
    )
    return translation_template.format(**kwargs)


async def async_setup_entry(hass, config_entry):
    """Set up Appartme integration from a config entry.

    Args:
        hass: Home Assistant instance.
        config_entry: The configuration entry.

    Returns:
        True if setup was successful.

    """
    # Access the update interval from options, default to 60 seconds
    update_interval = config_entry.options.get(
        "update_interval", UPDATE_INTERVAL_DEFAULT
    )

    # Fetch translations for the current language using a relative path
    language = hass.config.language
    component_directory = os.path.dirname(__file__)
    translation_file = os.path.join(
        component_directory, f"translations/{language}.json"
    )

    # Read the translation file in an executor to avoid blocking the event loop
    try:
        translations = await hass.async_add_executor_job(
            read_translation_file, translation_file
        )
    except FileNotFoundError:
        _LOGGER.warning(
            "Translation file for language '%s' not found at path: %s",
            language,
            translation_file,
        )
        translations = {}

    session = async_get_clientsession(hass)
    access_token = config_entry.data["token"]["access_token"]
    api = AppartmePaasClient(access_token, session=session, api_url=API_URL)

    devices = await api.fetch_devices()
    devices_info = []
    coordinators = {}

    for device in devices:
        if device["type"] == "mm":
            device_id = device["deviceId"]

            # Fetch device details
            device_info = await api.fetch_device_details(device_id)
            if device_info is None:
                _LOGGER.warning(
                    "Could not fetch details for device %s. Skipping this device",
                    device_id,
                )
                continue  # Skip this device

            devices_info.append(device_info)

            # Create a coordinator for this device
            coordinator = AppartmeDataUpdateCoordinator(
                hass,
                api,
                device_id,
                device_info.get("name", "Unknown Device"),
                update_interval=timedelta(seconds=update_interval),
            )

            # Handle exceptions during initial refresh
            try:
                await coordinator.async_config_entry_first_refresh()
            except ConfigEntryNotReady as err:
                _LOGGER.warning(
                    "Initial data fetch failed for device %s: %s", device_id, err
                )
                # The coordinator will handle retries and set entities as unavailable
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Unexpected error during initial data fetch for device %s: %s",
                    device_id,
                    err,
                )

            coordinators[device_id] = coordinator

    # Store the devices and coordinators in hass.data for use in other platforms
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        "devices_info": devices_info,
        "api": api,
        "translations": translations,
        "coordinators": coordinators,
    }

    # Forward the setup to the individual platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload Appartme integration from a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok
