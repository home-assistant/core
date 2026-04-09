"""Tessie integration."""

import asyncio
import logging

from tesla_fleet_api.const import Scope
from tesla_fleet_api.exceptions import (
    Forbidden,
    GatewayTimeout,
    InvalidResponse,
    InvalidToken,
    MissingToken,
    RateLimited,
    ServiceUnavailable,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.tessie import Tessie

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MODELS
from .coordinator import (
    TessieEnergyHistoryCoordinator,
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

RETRY_EXCEPTIONS = (
    InvalidResponse,
    RateLimited,
    ServiceUnavailable,
    GatewayTimeout,
)


async def async_setup_entry(hass: HomeAssistant, entry: TessieConfigEntry) -> bool:
    """Set up Tessie config."""
    api_key = entry.data[CONF_ACCESS_TOKEN]
    session = async_get_clientsession(hass)
    tessie = Tessie(session, api_key)

    try:
        state_of_all_vehicles = await tessie.list_vehicles(only_active=True)
    except (InvalidToken, MissingToken) as e:
        raise ConfigEntryAuthFailed from e
    except RETRY_EXCEPTIONS as e:
        raise ConfigEntryNotReady from e
    except TeslaFleetError as e:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from e

    vehicles: list[TessieVehicleData] = []
    for vehicle in state_of_all_vehicles["results"]:
        if vehicle["last_state"] is None:
            continue

        vin = vehicle["vin"]
        vehicle_api = tessie.vehicles.create(vin)
        vehicles.append(
            TessieVehicleData(
                vin=vin,
                data_coordinator=TessieStateUpdateCoordinator(
                    hass,
                    entry,
                    api=vehicle_api,
                    api_key=api_key,
                    vin=vin,
                    data=vehicle["last_state"],
                ),
                device=DeviceInfo(
                    identifiers={(DOMAIN, vin)},
                    manufacturer="Tesla",
                    configuration_url="https://my.tessie.com/",
                    name=vehicle["last_state"]["display_name"],
                    model=MODELS.get(
                        vehicle["last_state"]["vehicle_config"]["car_type"],
                        vehicle["last_state"]["vehicle_config"]["car_type"],
                    ),
                    sw_version=vehicle["last_state"]["vehicle_state"][
                        "car_version"
                    ].split(" ")[0],
                    hw_version=vehicle["last_state"]["vehicle_config"]["driver_assist"],
                    serial_number=vin,
                ),
            )
        )

    # Energy Sites
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

                api = tessie.energySites.create(site_id)

                try:
                    live_status = (await api.live_status())["response"]
                except (InvalidToken, Forbidden, SubscriptionRequired) as e:
                    raise ConfigEntryAuthFailed from e
                except TeslaFleetError as e:
                    raise ConfigEntryNotReady(e.message) from e

                powerwall = (
                    product["components"]["battery"] or product["components"]["solar"]
                )

                energysites.append(
                    TessieEnergyData(
                        api=api,
                        id=site_id,
                        live_coordinator=(
                            TessieEnergySiteLiveCoordinator(
                                hass, entry, api, live_status
                            )
                            if isinstance(live_status, dict)
                            else None
                        ),
                        info_coordinator=TessieEnergySiteInfoCoordinator(
                            hass, entry, api
                        ),
                        history_coordinator=(
                            TessieEnergyHistoryCoordinator(hass, entry, api)
                            if powerwall
                            else None
                        ),
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
                if energysite.live_coordinator is not None
            ),
            *(
                energysite.info_coordinator.async_config_entry_first_refresh()
                for energysite in energysites
            ),
            *(
                energysite.history_coordinator.async_config_entry_first_refresh()
                for energysite in energysites
                if energysite.history_coordinator is not None
            ),
        )

    entry.runtime_data = TessieData(vehicles, energysites)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TessieConfigEntry) -> bool:
    """Unload Tessie Config."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
