"""The Ecobulles integration."""

from pyecobulles import EcobullesClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.util.dt import now as hass_now

from .const import DOMAIN
from .coordinator import EcobullesCoordinator
from .device import mac_from_eco_ref, model_from_serial_number

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EcobullesConfigEntry = ConfigEntry[EcobullesCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EcobullesConfigEntry) -> bool:
    """Set up Ecobulles from a config entry."""
    assert entry.unique_id is not None
    eco_ref = entry.unique_id
    boitier_name = entry.data.get("name")
    num_serie = entry.data.get("num_serie")
    firmware_version = entry.data.get("firmware_version")

    device_registry = dr.async_get(hass)
    mac_address = mac_from_eco_ref(eco_ref)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, eco_ref)},
        name=boitier_name,
        manufacturer="Ecobulles",
        model=model_from_serial_number(num_serie),
        sw_version=firmware_version,
        serial_number=num_serie,
        connections={(CONNECTION_NETWORK_MAC, mac_address)} if mac_address else set(),
    )

    coordinator = EcobullesCoordinator(
        hass,
        EcobullesClient(session=async_get_clientsession(hass), now_fn=hass_now),
        entry,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcobullesConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
