"""Teslemetry integration."""
import asyncio
from typing import Final

from tesla_fleet_api import Teslemetry, VehicleSpecific
from tesla_fleet_api.exceptions import InvalidToken, PaymentRequired, TeslaFleetError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER
from .coordinator import TeslemetryVehicleDataCoordinator
from .models import TeslemetryVehicleData

PLATFORMS: Final = [
    Platform.CLIMATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Teslemetry config."""

    access_token = entry.data[CONF_ACCESS_TOKEN]

    # Create API connection
    teslemetry = Teslemetry(
        session=async_get_clientsession(hass),
        access_token=access_token,
    )
    try:
        products = (await teslemetry.products())["response"]
    except InvalidToken:
        LOGGER.error("Access token is invalid, unable to connect to Teslemetry")
        return False
    except PaymentRequired:
        LOGGER.error("Subscription required, unable to connect to Telemetry")
        return False
    except TeslaFleetError as e:
        raise ConfigEntryNotReady from e

    # Create array of classes
    data = []
    for product in products:
        if "vin" not in product:
            continue
        vin = product["vin"]

        api = VehicleSpecific(teslemetry.vehicle, vin)
        coordinator = TeslemetryVehicleDataCoordinator(hass, api)
        data.append(
            TeslemetryVehicleData(
                api=api,
                coordinator=coordinator,
                vin=vin,
            )
        )

    # Do all coordinator first refresh simultaneously
    await asyncio.gather(
        *(vehicle.coordinator.async_config_entry_first_refresh() for vehicle in data)
    )

    # Setup Platforms
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Teslemetry Config."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
