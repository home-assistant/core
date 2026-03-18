"""The Easywave integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .const import (
    CONF_DEVICE_PATH,
    CONF_USB_PID,
    DOMAIN,
    get_frequency_for_pid,
    is_country_allowed_for_frequency,
)
from .coordinator import EasywaveCoordinator
from .transceiver import RX11Transceiver

_LOGGER = logging.getLogger(__name__)


@dataclass
class EasywaveRuntimeData:
    """Runtime data for the Easywave integration."""

    coordinator: EasywaveCoordinator
    frequency: str
    country: str


type EasywaveConfigEntry = ConfigEntry[EasywaveRuntimeData]

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> bool:
    """Set up Easywave from a config entry."""

    # ── Regulatory compliance check (868 MHz) ──────────────────────────
    # The operating frequency is derived from the USB device's PID.
    # If the configured HA country is outside the allowed region for that
    # frequency, the integration must not start.
    usb_pid = entry.data.get(CONF_USB_PID)
    frequency = get_frequency_for_pid(usb_pid)
    country_code = hass.config.country  # ISO 3166-1 alpha-2 or None

    if frequency and not is_country_allowed_for_frequency(frequency, country_code):
        _LOGGER.warning(
            "This hardware operates on %s, which is not permitted in "
            "your configured region (%s). Integration disabled for "
            "regulatory compliance",
            frequency,
            country_code or "unknown",
        )
        # Create a persistent repair issue visible in the HA dashboard
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"frequency_not_permitted_{entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="frequency_not_permitted",
            translation_placeholders={
                "frequency": frequency,
                "country": country_code or "unknown",
            },
        )
        # Return False for regulatory compliance violation (not a setup error)
        return False

    # If the check passed, make sure any stale repair issue is removed
    # (e.g. user changed their country setting).
    ir.async_delete_issue(hass, DOMAIN, f"frequency_not_permitted_{entry.entry_id}")

    # ── Initialize transceiver and coordinator ──────────────────────────
    # Create transceiver instance, prefer user-selected serial device_path
    transceiver = RX11Transceiver(hass, entry.data.get(CONF_DEVICE_PATH))

    # Create coordinator for managing connection lifecycle & offline mode
    coordinator = EasywaveCoordinator(hass, transceiver, entry)

    # Attempt initial setup (may succeed in offline mode)
    if not await coordinator.async_setup():
        raise ConfigEntryNotReady("Failed to initialize coordinator")

    # Set runtime data for the integration
    entry.runtime_data = EasywaveRuntimeData(
        coordinator=coordinator,
        frequency=frequency or "unknown",
        country=country_code or "unknown",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms first; only shut down the coordinator if this succeeds
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    if hasattr(entry, "runtime_data") and entry.runtime_data:
        await entry.runtime_data.coordinator.async_shutdown()

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removing devices except the RX11 gateway."""
    gateway_identifier = (DOMAIN, f"{config_entry.entry_id}_gateway")
    if gateway_identifier in device_entry.identifiers:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_delete_gateway",
        )
    return True
