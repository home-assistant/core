"""Besen BS20 Home Assistant integration."""

import logging

from besen_bs20.client import BesenBS20Client
from besen_bs20.exceptions import CannotConnect, InvalidAuth
from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .coordinator import BesenBS20Coordinator

type BesenBS20ConfigEntry = ConfigEntry[BesenBS20Coordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
) -> bool:
    """Set up Besen BS20 from a config entry."""

    address = entry.data[CONF_ADDRESS]
    pin = entry.data[CONF_PIN]

    def _ble_device_provider() -> BLEDevice | None:
        return bluetooth.async_ble_device_from_address(
            hass,
            address,
            connectable=True,
        )

    if _ble_device_provider() is None:
        reason = bluetooth.async_address_reachability_diagnostics(
            hass,
            address,
            BluetoothReachabilityIntent.CONNECTION,
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="no_connectable_path",
            translation_placeholders={"reason": reason},
        )

    client = BesenBS20Client(
        address=address,
        pin=pin,
        ble_device_provider=_ble_device_provider,
        logger=_LOGGER,
        advertised_name=entry.data.get(CONF_NAME),
    )
    coordinator = BesenBS20Coordinator(hass, entry, client)

    try:
        await coordinator.async_start()
    except InvalidAuth as err:
        raise ConfigEntryAuthFailed from err
    except CannotConnect as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
) -> bool:
    """Unload a Besen BS20 config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
    return unload_ok
