"""Tessie integration."""

import asyncio
from http import HTTPStatus
import logging

from aiohttp import ClientError, ClientResponseError
from tesla_fleet_api import EnergySpecific, Tessie
from tesla_fleet_api.const import Scope
from tesla_fleet_api.exceptions import TeslaFleetError
from tessie_api import get_state_of_all_vehicles

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MODELS
from .coordinator import (
    TessieEnergySiteInfoCoordinator,
    TessieEnergySiteLiveCoordinator,
    TessieStateUpdateCoordinator,
)
from .models import TessieData, TessieEnergyData, TessieVehicleData

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

_LOGGER = logging.getLogger(__name__)

type TessieConfigEntry = ConfigEntry[TessieData]


async def async_setup_entry(hass: HomeAssistant, entry: TessieConfigEntry) -> bool:
    """Set up Tessie config."""
    api_key = entry.data[CONF_ACCESS_TOKEN]
    session = async_get_clientsession(hass)

    try:
        state_of_all_vehicles = await get_state_of_all_vehicles(
            session=session,
            api_key=api_key,
            only_active=True,
        )
    except ClientResponseError as e:
        if e.status == HTTPStatus.UNAUTHORIZED:
            raise ConfigEntryAuthFailed from e
        _LOGGER.error("Setup failed, unable to connect to Tessie: %s", e)
        return False
    except ClientError as e:
        raise ConfigEntryNotReady from e

    vehicles = [
        TessieVehicleData(
            vin=vehicle["vin"],
            data_coordinator=TessieStateUpdateCoordinator(
                hass,
                api_key=api_key,
                vin=vehicle["vin"],
                data=vehicle["last_state"],
            ),
            device=DeviceInfo(
                identifiers={(DOMAIN, vehicle["vin"])},
                manufacturer="Tesla",
                configuration_url="https://my.tessie.com/",
                name=vehicle["last_state"]["display_name"],
                model=MODELS.get(
                    vehicle["last_state"]["vehicle_config"]["car_type"],
                    vehicle["last_state"]["vehicle_config"]["car_type"],
                ),
                sw_version=vehicle["last_state"]["vehicle_state"]["car_version"].split(
                    " "
                )[0],
                hw_version=vehicle["last_state"]["vehicle_config"]["driver_assist"],
                serial_number=vehicle["vin"],
            ),
        )
        for vehicle in state_of_all_vehicles["results"]
        if vehicle["last_state"] is not None
    ]

    # Energy Sites
    tessie = Tessie(session, api_key)
    energysites: list[TessieEnergyData] = []

    try:
        scopes = await tessie.scopes()
    except TeslaFleetError as e:
        raise ConfigEntryNotReady from e

    if Scope.ENERGY_DEVICE_DATA in scopes:
        try:
            products = (await tessie.products())["response"]
        except TeslaFleetError as e:
            raise ConfigEntryNotReady from e

        for product in products:
            if "energy_site_id" in product:
                site_id = product["energy_site_id"]
                if not (
                    product["components"]["battery"]
                    or product["components"]["solar"]
                    or "wall_connectors" in product["components"]
                ):
                    _LOGGER.debug(
                        "Skipping Energy Site %s as it has no components",
                        site_id,
                    )
                    continue

                api = EnergySpecific(tessie.energy, site_id)
                energysites.append(
                    TessieEnergyData(
                        api=api,
                        id=site_id,
                        live_coordinator=TessieEnergySiteLiveCoordinator(hass, api),
                        info_coordinator=TessieEnergySiteInfoCoordinator(hass, api),
                        device=DeviceInfo(
                            identifiers={(DOMAIN, str(site_id))},
                            manufacturer="Tesla",
                            name=product.get("site_name", "Energy Site"),
                        ),
                    )
                )

        # Populate coordinator data before forwarding to platforms
        await asyncio.gather(
            *(
                energysite.live_coordinator.async_config_entry_first_refresh()
                for energysite in energysites
            ),
            *(
                energysite.info_coordinator.async_config_entry_first_refresh()
                for energysite in energysites
            ),
        )

    entry.runtime_data = TessieData(vehicles, energysites)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TessieConfigEntry) -> bool:
    """Unload Tessie Config."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
