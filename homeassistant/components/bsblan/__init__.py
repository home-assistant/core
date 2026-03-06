"""The BSB-LAN integration."""

import asyncio
import dataclasses

from bsblan import (
    BSBLAN,
    BSBLANAuthError,
    BSBLANConfig,
    BSBLANConnectionError,
    BSBLANError,
    Device,
    Info,
    StaticState,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_HEATING_CIRCUITS, CONF_PASSKEY, DOMAIN
from .coordinator import BSBLanFastCoordinator, BSBLanSlowCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.BUTTON, Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type BSBLanConfigEntry = ConfigEntry[BSBLanData]


@dataclasses.dataclass
class BSBLanData:
    """BSBLan data stored in the Home Assistant data object."""

    fast_coordinator: BSBLanFastCoordinator
    slow_coordinator: BSBLanSlowCoordinator
    client: BSBLAN
    device: Device
    info: Info
    static: dict[int, StaticState]
    available_circuits: list[int]


def get_bsblan_device_info(device: Device, info: Info, host: str) -> DeviceInfo:
    """Build DeviceInfo for the main BSB-LAN controller device."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.MAC)},
        connections={(CONNECTION_NETWORK_MAC, format_mac(device.MAC))},
        name=device.name,
        manufacturer="BSBLAN Inc.",
        model=(
            info.device_identification.value
            if info.device_identification and info.device_identification.value
            else None
        ),
        model_id=(
            f"{info.controller_family.value}_{info.controller_variant.value}"
            if info.controller_family
            and info.controller_variant
            and info.controller_family.value
            and info.controller_variant.value
            else None
        ),
        sw_version=device.version,
        configuration_url=f"http://{host}",
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the BSB-LAN integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BSBLanConfigEntry) -> bool:
    """Set up BSB-LAN from a config entry."""

    # create config using BSBLANConfig
    config = BSBLANConfig(
        host=entry.data[CONF_HOST],
        passkey=entry.data[CONF_PASSKEY],
        port=entry.data[CONF_PORT],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    # create BSBLAN client
    session = async_get_clientsession(hass)
    bsblan = BSBLAN(config, session)

    try:
        # Initialize the client first - this sets up internal caches and validates
        # the connection by fetching firmware version
        await bsblan.initialize()

        # Read configured heating circuits from config entry (discovered in config flow)
        circuits: list[int] = entry.data.get(CONF_HEATING_CIRCUITS, [1])

        # Fetch device metadata in parallel for faster startup
        device, info = await asyncio.gather(
            bsblan.device(),
            bsblan.info(),
        )

        # Fetch static values per configured circuit
        static_per_circuit: dict[int, StaticState] = {}
        for circuit in circuits:
            static_per_circuit[circuit] = await bsblan.static_values(circuit=circuit)
    except BSBLANConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    except BSBLANAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="setup_auth_error",
        ) from err
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    except BSBLANError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="setup_general_error",
        ) from err

    # Create coordinators with the already-initialized client
    fast_coordinator = BSBLanFastCoordinator(hass, entry, bsblan)
    slow_coordinator = BSBLanSlowCoordinator(hass, entry, bsblan)

    # Perform first refresh of fast coordinator (required for entities)
    await fast_coordinator.async_config_entry_first_refresh()

    # Refresh slow coordinator - don't fail if DHW is not available
    # This allows the integration to work even if the device doesn't support DHW
    await slow_coordinator.async_refresh()

    entry.runtime_data = BSBLanData(
        client=bsblan,
        fast_coordinator=fast_coordinator,
        slow_coordinator=slow_coordinator,
        device=device,
        info=info,
        static=static_per_circuit,
        available_circuits=circuits,
    )

    # Register main device before forwarding platforms, so sub-devices
    # (heating circuits, water heater) can reference it via via_device
    device_registry = dr.async_get(hass)
    main_device_info = get_bsblan_device_info(device, info, entry.data[CONF_HOST])
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=main_device_info["identifiers"],
        connections=main_device_info["connections"],
        name=main_device_info["name"],
        manufacturer=main_device_info["manufacturer"],
        model=main_device_info.get("model"),
        model_id=main_device_info.get("model_id"),
        sw_version=main_device_info.get("sw_version"),
        configuration_url=main_device_info.get("configuration_url"),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BSBLanConfigEntry) -> bool:
    """Unload BSBLAN config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
