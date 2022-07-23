"""Support for Switchbot devices."""

from types import MappingProxyType
from typing import Any

import switchbot

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_BOT,
    ATTR_CURTAIN,
    ATTR_HYGROMETER,
    COMMON_OPTIONS,
    CONF_RETRY_COUNT,
    CONF_RETRY_TIMEOUT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_TIMEOUT,
    DEPRECATED_CONFIG_OPTIONS,
    DOMAIN,
)
from .coordinator import SwitchbotCoordinator

PLATFORMS_BY_TYPE = {
    ATTR_BOT: [Platform.SWITCH, Platform.SENSOR],
    ATTR_CURTAIN: [Platform.COVER, Platform.BINARY_SENSOR, Platform.SENSOR],
    ATTR_HYGROMETER: [Platform.SENSOR],
}
CLASS_BY_DEVICE = {
    ATTR_CURTAIN: switchbot.SwitchbotCurtain,
    ATTR_BOT: switchbot.Switchbot,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Switchbot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    domain_data = hass.data[DOMAIN]

    if CONF_MAC in entry.data:
        # Bleak uses addresses not mac addresses which are are actually
        # UUIDs on some platforms (MacOS).
        mac = entry.data[CONF_MAC]
        if "-" not in mac:
            mac = dr.format_mac(mac).upper()
        hass.config_entries.async_update_entry(
            entry,
            data={k: v for k, v in entry.data.items() if k != CONF_MAC}
            | {CONF_ADDRESS: mac},
        )

    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT,
                CONF_RETRY_TIMEOUT: DEFAULT_RETRY_TIMEOUT,
            },
        )

    if DEPRECATED_CONFIG_OPTIONS.intersection(entry.options):
        hass.config_entries.async_update_entry(
            entry,
            options={
                k: v
                for k, v in entry.options.items()
                if k not in DEPRECATED_CONFIG_OPTIONS
            },
        )

    sensor_type = entry.data[CONF_SENSOR_TYPE]
    address = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Switchbot {sensor_type} with address {address}"
        )

    if COMMON_OPTIONS not in domain_data:
        domain_data[COMMON_OPTIONS] = entry.options

    common_options: dict[str, int] = domain_data[COMMON_OPTIONS]
    switchbot.DEFAULT_RETRY_TIMEOUT = common_options[CONF_RETRY_TIMEOUT]

    cls = CLASS_BY_DEVICE.get(sensor_type, switchbot.SwitchbotDevice)
    device = cls(
        device=ble_device,
        password=entry.data.get(CONF_PASSWORD),
        retry_count=entry.options[CONF_RETRY_COUNT],
    )
    coordinator = hass.data[DOMAIN][entry.entry_id] = SwitchbotCoordinator(
        hass, ble_device=ble_device, device=device, common_options=common_options
    )
    entry.async_on_unload(coordinator.async_start())
    if not await coordinator.async_wait_ready():
        raise ConfigEntryNotReady(f"Switchbot {sensor_type} with {address} not ready")

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    sensor_type = entry.data[CONF_SENSOR_TYPE]
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.config_entries.async_entries(DOMAIN):
            hass.data.pop(DOMAIN)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Update entity options stored in hass.
    common_options: MappingProxyType[str, Any] = hass.data[DOMAIN][COMMON_OPTIONS]
    if entry.options != common_options:
        await hass.config_entries.async_reload(entry.entry_id)
