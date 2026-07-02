"""Besen BS20 Home Assistant integration."""

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from besen_bs20.client import BesenBS20Client
from besen_bs20.exceptions import CannotConnect, InvalidAuth

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK, DOMAIN, PLATFORMS
from .coordinator import BesenBS20Coordinator
from .repairs import (
    async_create_no_connectable_path_issue,
    async_create_reauth_issue,
    async_delete_no_connectable_path_issue,
    async_delete_reauth_issue,
)

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


@dataclass(slots=True)
class BesenBS20RuntimeData:
    """Runtime data for a Besen BS20 config entry."""

    client: BesenBS20Client
    coordinator: BesenBS20Coordinator


if TYPE_CHECKING:
    type BesenBS20ConfigEntry = ConfigEntry[BesenBS20RuntimeData]
else:
    BesenBS20ConfigEntry = object

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
) -> bool:
    """Set up Besen BS20 from a config entry."""

    address = entry.data[CONF_ADDRESS]
    pin = entry.data[CONF_PIN]
    sync_clock = entry.options.get(
        CONF_SYNC_CLOCK,
        entry.data.get(CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK),
    )

    def _ble_device_provider() -> BLEDevice | None:
        return bluetooth.async_ble_device_from_address(
            hass,
            address,
            connectable=True,
        )

    if _ble_device_provider() is None:
        async_create_no_connectable_path_issue(hass, entry.entry_id)
        reason = "No connectable Bluetooth path is available"
        diagnostics = getattr(
            bluetooth,
            "async_address_reachability_diagnostics",
            None,
        )
        intent = getattr(
            getattr(bluetooth, "BluetoothReachabilityIntent", object),
            "CONNECTION",
            None,
        )
        if callable(diagnostics) and intent is not None:
            reason = diagnostics(hass, address, intent)
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
        sync_clock=sync_clock,
    )
    coordinator = BesenBS20Coordinator(hass, client)

    try:
        await coordinator.async_start()
    except InvalidAuth as err:
        async_create_reauth_issue(hass, entry.entry_id)
        raise ConfigEntryAuthFailed from err
    except CannotConnect as err:
        async_create_no_connectable_path_issue(hass, entry.entry_id)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    async_delete_no_connectable_path_issue(hass, entry.entry_id)
    async_delete_reauth_issue(hass, entry.entry_id)
    entry.runtime_data = BesenBS20RuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
) -> bool:
    """Unload a Besen BS20 config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.coordinator.async_shutdown()
    return unload_ok
