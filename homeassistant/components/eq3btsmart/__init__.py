"""Support for EQ3 devices."""

from eq3btsmart import Thermostat
from eq3btsmart.thermostat_config import ThermostatConfig

from homeassistant.components import bluetooth
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_CURRENT_TEMP_SELECTOR,
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_MAC_ADDRESS,
    CONF_TARGET_TEMP_SELECTOR,
    DEFAULT_CURRENT_TEMP_SELECTOR,
    DEFAULT_TARGET_TEMP_SELECTOR,
)
from .coordinator import Eq3ConfigEntry, Eq3ConfigEntryData, Eq3Coordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: Eq3ConfigEntry) -> bool:
    """Handle config entry setup."""

    mac_address: str = entry.data.get(CONF_MAC_ADDRESS, entry.unique_id)

    device = bluetooth.async_ble_device_from_address(
        hass, mac_address.upper(), connectable=True
    )

    if device is None:
        raise ConfigEntryNotReady(f"[{mac_address}] Device could not be found")

    thermostat = Thermostat(
        thermostat_config=ThermostatConfig(
            mac_address=mac_address,
        ),
        ble_device=device,
    )

    if not entry.data:
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_MAC_ADDRESS: mac_address},
        )

    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                CONF_CURRENT_TEMP_SELECTOR: DEFAULT_CURRENT_TEMP_SELECTOR,
                CONF_TARGET_TEMP_SELECTOR: DEFAULT_TARGET_TEMP_SELECTOR,
                CONF_EXTERNAL_TEMP_SENSOR: None,
            },
        )

    coordinator = Eq3Coordinator(hass, entry, mac_address)

    entry.runtime_data = Eq3ConfigEntryData(
        thermostat=thermostat, coordinator=coordinator
    )
    entry.async_on_unload(entry.add_update_listener(update_listener))

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Eq3ConfigEntry) -> bool:
    """Handle config entry unload."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.thermostat.async_disconnect()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: Eq3ConfigEntry) -> None:
    """Handle config entry update."""

    await hass.config_entries.async_reload(entry.entry_id)
