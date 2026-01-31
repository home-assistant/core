"""The LoJack integration."""

from __future__ import annotations

from lojack_api import ApiError, AuthenticationError, LoJackClient

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import LOGGER
from .coordinator import LoJackConfigEntry, LoJackCoordinator, LoJackData

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: LoJackConfigEntry) -> bool:
    """Set up LoJack from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        client = await LoJackClient.create(username, password)
        devices = await client.list_devices()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed("Invalid authentication credentials") from err
    except ApiError as err:
        raise ConfigEntryNotReady(f"Error connecting to LoJack API: {err}") from err

    coordinators: dict[str, LoJackCoordinator] = {}

    for device in devices:
        device_id = str(getattr(device, "id", ""))
        if not device_id:
            continue

        # Get initial location data
        try:
            location = await device.get_location()
            device.location = {
                "coordinates": {
                    "latitude": getattr(location, "latitude", None),
                    "longitude": getattr(location, "longitude", None),
                },
                "accuracy": getattr(location, "accuracy", None),
                "address": getattr(location, "address", None),
                "speed": getattr(location, "speed", None),
                "heading": getattr(location, "heading", None),
                "battery_voltage": getattr(location, "battery_voltage", None),
                "engine_hours": getattr(location, "engine_hours", None),
                "timestamp": getattr(location, "timestamp", None),
            }
        except Exception:  # noqa: BLE001
            LOGGER.debug("Could not get initial location for device %s", device_id)
            device.location = {}

        coordinator = LoJackCoordinator(
            hass,
            entry,
            client,
            device_id,
            {
                "name": getattr(device, "name", None),
                "vin": getattr(device, "vin", None),
                "make": getattr(device, "make", None),
                "model": getattr(device, "model", None),
                "year": getattr(device, "year", None),
                "color": getattr(device, "color", None),
                "license_plate": getattr(device, "license_plate", None),
                "odometer": getattr(device, "odometer", None),
                "location": device.location,
            },
        )

        await coordinator.async_config_entry_first_refresh()
        coordinators[device_id] = coordinator

    entry.runtime_data = LoJackData(client=client, coordinators=coordinators)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LoJackConfigEntry) -> bool:
    """Unload a LoJack config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Close the client connection
        if entry.runtime_data:
            await entry.runtime_data.client.close()

    return unload_ok
