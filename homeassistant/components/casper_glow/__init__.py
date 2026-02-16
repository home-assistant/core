"""The Casper Glow integration."""

from __future__ import annotations

from pycasperglow import CasperGlow

from homeassistant.components import bluetooth
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SERVICE_PAUSE, SERVICE_RESUME
from .coordinator import CasperGlowCoordinator
from .models import CasperGlowConfigEntry, CasperGlowData

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.LIGHT]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Casper Glow services."""
    for service_name, method in (
        (SERVICE_PAUSE, "async_pause"),
        (SERVICE_RESUME, "async_resume"),
    ):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            service_name,
            entity_domain=LIGHT_DOMAIN,
            schema={},
            func=method,
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Casper Glow integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: CasperGlowConfigEntry) -> bool:
    """Set up Casper Glow from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Casper Glow device with address {address}"
        )

    glow = CasperGlow(ble_device)
    coordinator = CasperGlowCoordinator(hass, glow, entry.title)
    entry.runtime_data = CasperGlowData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CasperGlowConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: CasperGlowConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    return True
