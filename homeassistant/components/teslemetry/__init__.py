"""Teslemetry integration."""

import asyncio
from collections.abc import Callable
from typing import Final

from tesla_fleet_api import EnergySpecific, Teslemetry, VehicleSpecific
from tesla_fleet_api.const import Scope
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
)
from teslemetry_stream import TeslemetryStream

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, MODELS
from .coordinator import (
    TeslemetryEnergyHistoryCoordinator,
    TeslemetryEnergySiteInfoCoordinator,
    TeslemetryEnergySiteLiveCoordinator,
    TeslemetryVehicleDataCoordinator,
)
from .helpers import flatten
from .models import TeslemetryData, TeslemetryEnergyData, TeslemetryVehicleData
from .services import async_register_services

PLATFORMS: Final = [
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

type TeslemetryConfigEntry = ConfigEntry[TeslemetryData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Telemetry integration."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TeslemetryConfigEntry) -> bool:
    """Set up Teslemetry config."""

    access_token = entry.data[CONF_ACCESS_TOKEN]
    session = async_get_clientsession(hass)

    # Create API connection
    teslemetry = Teslemetry(
        session=session,
        access_token=access_token,
    )
    try:
        calls = await asyncio.gather(
            teslemetry.metadata(),
            teslemetry.products(),
        )
    except InvalidToken as e:
        raise ConfigEntryAuthFailed from e
    except SubscriptionRequired as e:
        raise ConfigEntryAuthFailed from e
    except TeslaFleetError as e:
        raise ConfigEntryNotReady from e

    scopes = calls[0]["scopes"]
    region = calls[0]["region"]
    products = calls[1]["response"]

    device_registry = dr.async_get(hass)

    # Create array of classes
    vehicles: list[TeslemetryVehicleData] = []
    energysites: list[TeslemetryEnergyData] = []

    # Create the stream
    stream = TeslemetryStream(
        session,
        access_token,
        server=f"{region.lower()}.teslemetry.com",
        parse_timestamp=True,
    )

    for product in products:
        if "vin" in product and Scope.VEHICLE_DEVICE_DATA in scopes:
            # Remove the protobuff 'cached_data' that we do not use to save memory
            product.pop("cached_data", None)
            vin = product["vin"]
            api = VehicleSpecific(teslemetry.vehicle, vin)
            coordinator = TeslemetryVehicleDataCoordinator(hass, api, product)
            device = DeviceInfo(
                identifiers={(DOMAIN, vin)},
                manufacturer="Tesla",
                configuration_url="https://teslemetry.com/console",
                name=product["display_name"],
                model=MODELS.get(vin[3]),
                serial_number=vin,
            )

            remove_listener = stream.async_add_listener(
                create_handle_vehicle_stream(vin, coordinator),
                {"vin": vin},
            )

            vehicles.append(
                TeslemetryVehicleData(
                    api=api,
                    coordinator=coordinator,
                    stream=stream,
                    vin=vin,
                    device=device,
                    remove_listener=remove_listener,
                )
            )

        elif "energy_site_id" in product and Scope.ENERGY_DEVICE_DATA in scopes:
            site_id = product["energy_site_id"]
            powerwall = (
                product["components"]["battery"] or product["components"]["solar"]
            )
            wall_connector = "wall_connectors" in product["components"]
            if not powerwall and not wall_connector:
                LOGGER.debug(
                    "Skipping Energy Site %s as it has no components",
                    site_id,
                )
                continue

            api = EnergySpecific(teslemetry.energy, site_id)
            device = DeviceInfo(
                identifiers={(DOMAIN, str(site_id))},
                manufacturer="Tesla",
                configuration_url="https://teslemetry.com/console",
                name=product.get("site_name", "Energy Site"),
                serial_number=str(site_id),
            )

            energysites.append(
                TeslemetryEnergyData(
                    api=api,
                    live_coordinator=TeslemetryEnergySiteLiveCoordinator(hass, api),
                    info_coordinator=TeslemetryEnergySiteInfoCoordinator(
                        hass, api, product
                    ),
                    history_coordinator=(
                        TeslemetryEnergyHistoryCoordinator(hass, api)
                        if powerwall
                        else None
                    ),
                    id=site_id,
                    device=device,
                )
            )

    # Run all first refreshes
    await asyncio.gather(
        *(
            vehicle.coordinator.async_config_entry_first_refresh()
            for vehicle in vehicles
        ),
        *(
            energysite.live_coordinator.async_config_entry_first_refresh()
            for energysite in energysites
        ),
        *(
            energysite.info_coordinator.async_config_entry_first_refresh()
            for energysite in energysites
        ),
        *(
            energysite.history_coordinator.async_config_entry_first_refresh()
            for energysite in energysites
            if energysite.history_coordinator
        ),
    )

    # Add energy device models
    for energysite in energysites:
        models = set()
        for gateway in energysite.info_coordinator.data.get("components_gateways", []):
            if gateway.get("part_name"):
                models.add(gateway["part_name"])
        for battery in energysite.info_coordinator.data.get("components_batteries", []):
            if battery.get("part_name"):
                models.add(battery["part_name"])
        if models:
            energysite.device["model"] = ", ".join(sorted(models))

        # Create the energy site device regardless of it having entities
        # This is so users with a Wall Connector but without a Powerwall can still make service calls
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **energysite.device
        )

    # Setup Platforms
    entry.runtime_data = TeslemetryData(vehicles, energysites, scopes)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeslemetryConfigEntry) -> bool:
    """Unload Teslemetry Config."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry."""
    if config_entry.version > 1:
        return False

    if config_entry.version == 1 and config_entry.minor_version < 2:
        # Add unique_id to existing entry
        teslemetry = Teslemetry(
            session=async_get_clientsession(hass),
            access_token=config_entry.data[CONF_ACCESS_TOKEN],
        )
        try:
            metadata = await teslemetry.metadata()
        except TeslaFleetError as e:
            LOGGER.error(e.message)
            return False

        hass.config_entries.async_update_entry(
            config_entry, unique_id=metadata["uid"], version=1, minor_version=2
        )
    return True


def create_handle_vehicle_stream(vin: str, coordinator) -> Callable[[dict], None]:
    """Create a handle vehicle stream function."""

    def handle_vehicle_stream(data: dict) -> None:
        """Handle vehicle data from the stream."""
        if "vehicle_data" in data:
            LOGGER.debug("Streaming received vehicle data from %s", vin)
            coordinator.async_set_updated_data(flatten(data["vehicle_data"]))
        elif "state" in data:
            LOGGER.debug("Streaming received state from %s", vin)
            coordinator.data["state"] = data["state"]
            coordinator.async_set_updated_data(coordinator.data)

    return handle_vehicle_stream
