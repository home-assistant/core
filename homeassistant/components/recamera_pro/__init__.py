"""reCamera Pro integration."""

import logging
import re

from recamera_protocol import (
    RecameraError,
    normalize_mac_address,
    normalize_serial_number,
)

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import (
    CONF_HW_VERSION,
    CONF_MAC_ADDRESS,
    CONF_MODEL,
    CONF_SERIAL_NUMBER,
    CONF_SW_VERSION,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import RecameraConfigEntry, RecameraCoordinator, async_remove_store
from .identity import device_title

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: RecameraConfigEntry
) -> None:
    """Set up one reCamera Pro from a config entry."""
    _normalize_entry_title(hass, config_entry)
    coordinator = RecameraCoordinator(hass, config_entry)
    try:
        await coordinator.async_setup()
        await _async_refresh_entry_identity(
            hass,
            config_entry,
            coordinator,
        )
        config_entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        raise


def _normalize_entry_title(
    hass: HomeAssistant, config_entry: RecameraConfigEntry
) -> None:
    """Keep the integration title aligned with the current identity policy."""
    title = device_title(
        config_entry.data.get(CONF_SERIAL_NUMBER),
        config_entry.data.get(CONF_MAC_ADDRESS),
        fallback=config_entry.data.get(CONF_HOST),
    )
    current = config_entry.title
    legacy_default = (
        current == str(config_entry.data.get(CONF_HOST) or "")
        or current in {"reCamera-Test", "reCamera Pro"}
        or re.fullmatch(r"reCamera Pro \([0-9A-Fa-f:._-]{6,}\)", current) is not None
        or re.fullmatch(
            r"reCamera Pro [0-9A-Fa-f]{16}",
            current,
        )
        is not None
    )
    if legacy_default and current != title:
        hass.config_entries.async_update_entry(config_entry, title=title)


async def _async_refresh_entry_identity(
    hass: HomeAssistant,
    config_entry: RecameraConfigEntry,
    coordinator: RecameraCoordinator,
) -> None:
    """Backfill hardware identity for upgraded entries and reject mismatch."""
    stored_mac = normalize_mac_address(config_entry.data.get(CONF_MAC_ADDRESS))
    try:
        discovered_mac = await coordinator.client.async_get_network_identity()
    except RecameraError as err:
        if stored_mac:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="identity_confirm_failed",
            ) from err
        discovered_mac = None
    detected_mac = normalize_mac_address(discovered_mac)
    if stored_mac and detected_mac and stored_mac != detected_mac:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="identity_mac_mismatch",
        )
    if stored_mac and detected_mac is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="identity_mac_missing",
        )

    info = (
        coordinator.data.info
        if coordinator.data is not None
        else coordinator.client.info
    )
    stored_serial = normalize_serial_number(config_entry.data.get(CONF_SERIAL_NUMBER))
    mac_matches = bool(stored_mac and detected_mac and stored_mac == detected_mac)
    if stored_serial:
        if info.serial_number:
            if stored_serial != info.serial_number:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="identity_serial_mismatch",
                )
        elif not mac_matches:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="identity_mac_mismatch",
            )
    if not stored_mac and not stored_serial and not detected_mac:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="identity_missing",
        )
    updates = {
        **config_entry.data,
        CONF_MAC_ADDRESS: detected_mac or stored_mac,
        CONF_SERIAL_NUMBER: info.serial_number or stored_serial or None,
        CONF_MODEL: info.base_plate_model or config_entry.data.get(CONF_MODEL),
        CONF_HW_VERSION: (
            info.hardware_version
            or info.sensor_model
            or config_entry.data.get(CONF_HW_VERSION)
        ),
        CONF_SW_VERSION: (
            info.firmware_version or config_entry.data.get(CONF_SW_VERSION)
        ),
    }
    if updates != dict(config_entry.data):
        hass.config_entries.async_update_entry(
            config_entry,
            data=updates,
        )
        _normalize_entry_title(hass, config_entry)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: RecameraConfigEntry
) -> None:
    """Unload a reCamera Pro entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
    coordinator: RecameraCoordinator | None = getattr(
        config_entry, "runtime_data", None
    )
    if coordinator is not None:
        await coordinator.async_shutdown()


async def async_remove_entry(
    hass: HomeAssistant, config_entry: RecameraConfigEntry
) -> None:
    """Remove persisted dynamic entity metadata."""
    await async_remove_store(hass, config_entry.entry_id)
    await Store(
        hass,
        1,
        f"{DOMAIN}.capture.{config_entry.entry_id}",
    ).async_remove()
