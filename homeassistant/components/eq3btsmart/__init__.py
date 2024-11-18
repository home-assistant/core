"""Support for EQ3 devices."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from eq3btsmart import Thermostat
from eq3btsmart.thermostat_config import ThermostatConfig

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import Eq3Coordinator
from .models import Eq3Config

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass(slots=True)
class Eq3ConfigEntryData:
    """Config entry for a single eQ-3 device."""

    eq3_config: Eq3Config
    thermostat: Thermostat
    coordinator: Eq3Coordinator


type Eq3ConfigEntry = ConfigEntry[Eq3ConfigEntryData]


async def async_setup_entry(hass: HomeAssistant, entry: Eq3ConfigEntry) -> bool:
    """Handle config entry setup."""

    mac_address: str | None = entry.unique_id

    if TYPE_CHECKING:
        assert mac_address is not None

    eq3_config = Eq3Config(
        mac_address=mac_address,
    )

    device = bluetooth.async_ble_device_from_address(
        hass, mac_address.upper(), connectable=True
    )

    if device is None:
        raise ConfigEntryNotReady(
            f"[{eq3_config.mac_address}] Device could not be found"
        )

    thermostat = Thermostat(
        thermostat_config=ThermostatConfig(
            mac_address=mac_address,
        ),
        ble_device=device,
    )
    coordinator = Eq3Coordinator(hass, thermostat, mac_address)

    entry.runtime_data = Eq3ConfigEntryData(
        eq3_config=eq3_config, thermostat=thermostat, coordinator=coordinator
    )
    entry.async_on_unload(entry.add_update_listener(update_listener))

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_update_listeners()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Eq3ConfigEntry) -> bool:
    """Handle config entry unload."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.thermostat.async_disconnect()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: Eq3ConfigEntry) -> None:
    """Handle config entry update."""

    await hass.config_entries.async_reload(entry.entry_id)
