"""Tesla Fleet integration."""

import asyncio
from typing import TYPE_CHECKING, Final

import jwt
from tesla_fleet_api import EnergySpecific, TeslaFleetApi, VehicleSpecific
from tesla_fleet_api.const import Scope
from tesla_fleet_api.exceptions import (
    InvalidToken,
    LoginRequired,
    OAuthExpired,
    TeslaFleetError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, LOGGER, MODELS
from .coordinator import (
    TeslaFleetEnergySiteInfoCoordinator,
    TeslaFleetEnergySiteLiveCoordinator,
    TeslaFleetVehicleDataCoordinator,
)
from .models import TeslaFleetData, TeslaFleetEnergyData, TeslaFleetVehicleData

PLATFORMS: Final = [
    # Platform.BINARY_SENSOR,
    # Platform.BUTTON,
    # Platform.CLIMATE,
    # Platform.COVER,
    # Platform.DEVICE_TRACKER,
    # Platform.LOCK,
    # Platform.MEDIA_PLAYER,
    # Platform.NUMBER,
    # Platform.SELECT,
    Platform.SENSOR,
    # Platform.SWITCH,
    # Platform.UPDATE,
]

type TeslaFleetConfigEntry = ConfigEntry[TeslaFleetData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: TeslaFleetConfigEntry) -> bool:
    """Set up TeslaFleet config."""

    access_token = entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
    # refresh_token = entry.data[CONF_TOKEN][CONF_REFRESH_TOKEN]
    session = async_get_clientsession(hass)

    token = jwt.decode(
        entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN], options={"verify_signature": False}
    )
    scopes = token["scp"]
    region = token["ou_code"].lower()

    # Setup OAuth refresh
    implementation = await async_get_config_entry_implementation(hass, entry)
    oauth_session = OAuth2Session(hass, entry, implementation)
    refresh_lock = asyncio.Lock()

    async def _refresh_token() -> str:
        async with refresh_lock:
            LOGGER.info("Refreshing token")
            await oauth_session.async_ensure_token_valid()
            token = oauth_session.token[CONF_ACCESS_TOKEN]
            if TYPE_CHECKING:
                assert isinstance(token, str)
            return token

    # Create API connection
    tesla = TeslaFleetApi(
        session=session,
        access_token=access_token,
        region=region,
        charging_scope=False,
        partner_scope=False,
        user_scope=False,
        energy_scope=Scope.ENERGY_DEVICE_DATA in scopes,
        vehicle_scope=Scope.VEHICLE_DEVICE_DATA in scopes,
        refresh_hook=_refresh_token,
    )
    try:
        products = (await tesla.products())["response"]
    except (InvalidToken, OAuthExpired, LoginRequired) as e:
        raise ConfigEntryAuthFailed from e
    except TeslaFleetError as e:
        raise ConfigEntryNotReady from e

    device_registry = dr.async_get(hass)

    # Create array of classes
    vehicles: list[TeslaFleetVehicleData] = []
    energysites: list[TeslaFleetEnergyData] = []
    for product in products:
        if "vin" in product and tesla.vehicle:
            # Remove the protobuff 'cached_data' that we do not use to save memory
            product.pop("cached_data", None)
            vin = product["vin"]
            api = VehicleSpecific(tesla.vehicle, vin)
            coordinator = TeslaFleetVehicleDataCoordinator(hass, api, product)

            # await coordinator.async_config_entry_first_refresh()

            device = DeviceInfo(
                identifiers={(DOMAIN, vin)},
                manufacturer="Tesla",
                name=product["display_name"],
                model=MODELS.get(vin[3]),
                serial_number=vin,
            )

            vehicles.append(
                TeslaFleetVehicleData(
                    api=api,
                    coordinator=coordinator,
                    vin=vin,
                    device=device,
                )
            )
        elif "energy_site_id" in product and tesla.energy:
            site_id = product["energy_site_id"]
            api = EnergySpecific(tesla.energy, site_id)

            live_coordinator = TeslaFleetEnergySiteLiveCoordinator(hass, api)
            info_coordinator = TeslaFleetEnergySiteInfoCoordinator(hass, api, product)

            # Create energy site model
            model = None
            models = set()
            for gateway in product.get("components_gateways", []):
                if gateway.get("part_name"):
                    models.add(gateway["part_name"])
            for battery in product.get("components_batteries", []):
                if battery.get("part_name"):
                    models.add(battery["part_name"])
            if models:
                model = ", ".join(sorted(models))

            device = DeviceInfo(
                identifiers={(DOMAIN, str(site_id))},
                manufacturer="Tesla",
                name=product.get("site_name", "Energy Site"),
                model=model,
                serial_number=str(site_id),
            )

            # Create the energy site device regardless of it having entities
            # This is so users with a Wall Connector but without a Powerwall can still make service calls
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id, **device
            )

            energysites.append(
                TeslaFleetEnergyData(
                    api=api,
                    live_coordinator=live_coordinator,
                    info_coordinator=info_coordinator,
                    id=site_id,
                    device=device,
                )
            )

    # Setup Platforms
    entry.runtime_data = TeslaFleetData(vehicles, energysites, scopes)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeslaFleetConfigEntry) -> bool:
    """Unload TeslaFleet Config."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
