"""The Easywave integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .const import (
    CONF_USB_PID,
    DOMAIN,
    get_frequency_for_pid,
    is_country_allowed_for_frequency,
)

_LOGGER = logging.getLogger(__name__)

type EasywaveConfigEntry = ConfigEntry[None]

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> bool:
    """Set up Easywave from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # ── Regulatory compliance check (868 MHz) ──────────────────────────
    # The operating frequency is derived from the USB device's PID.
    # If the configured HA country is outside the allowed region for that
    # frequency, the integration must not start.
    usb_pid = entry.data.get(CONF_USB_PID)
    frequency = get_frequency_for_pid(usb_pid)
    country_code = hass.config.country  # ISO 3166-1 alpha-2 or None

    if frequency and not is_country_allowed_for_frequency(frequency, country_code):
        _LOGGER.warning(
            "This hardware operates on %s, which is not permitted in your "
            "configured region (%s). Integration disabled for regulatory compliance.",
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
        return False

    # If the check passed, make sure any stale repair issue is removed
    # (e.g. user changed their country setting).
    ir.async_delete_issue(hass, DOMAIN, f"frequency_not_permitted_{entry.entry_id}")
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EasywaveConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Prevent removing the RX11 gateway device via the UI device menu."""
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="cannot_delete_rx11",
    )
