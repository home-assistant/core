"""reCamera Pro integration."""

import json
import logging
from pathlib import Path
import re
from typing import Any

import probatio
from recamera_protocol import (
    RecameraError,
    normalize_mac_address,
    normalize_serial_number,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    service,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CAPTURE_OUTPUT,
    ATTR_RECORD_DURATION,
    CONF_HW_VERSION,
    CONF_MAC_ADDRESS,
    CONF_MODEL,
    CONF_SERIAL_NUMBER,
    CONF_SW_VERSION,
    DOMAIN,
    PLATFORMS,
    SERVICE_CAPTURE_DEVICE,
    SERVICE_RECORD_DEVICE,
    SERVICE_STOP_DEVICE_CAPTURE,
)
from .coordinator import RecameraCoordinator, async_remove_store
from .entity import effective_integration_language
from .identity import device_title

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration-wide actions."""
    _async_register_services(hass)
    return True


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration actions before any config entry loads."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CAPTURE_DEVICE,
        entity_domain="camera",
        schema={probatio.Optional(ATTR_CAPTURE_OUTPUT): str},
        func="async_capture_device_snapshot",
        supports_response=SupportsResponse.OPTIONAL,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RECORD_DEVICE,
        entity_domain="camera",
        schema={
            probatio.Optional(ATTR_CAPTURE_OUTPUT): str,
            probatio.Optional(ATTR_RECORD_DURATION, default=30): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=3600)
            ),
        },
        func="async_start_device_recording",
        supports_response=SupportsResponse.OPTIONAL,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_STOP_DEVICE_CAPTURE,
        entity_domain="camera",
        schema=None,
        func="async_stop_device_capture",
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
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
        await _async_sync_entity_registry_names(hass, config_entry, coordinator)
        loaded_language = effective_integration_language(hass, config_entry)

        @callback
        def _handle_core_config_update(_event: object) -> None:
            if effective_integration_language(hass, config_entry) != loaded_language:
                hass.async_create_task(
                    hass.config_entries.async_reload(config_entry.entry_id)
                )

        config_entry.async_on_unload(
            hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE,
                _handle_core_config_update,
            )
        )
    except BaseException:
        await coordinator.async_shutdown()
        raise
    return True


def _normalize_entry_title(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
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
    config_entry: ConfigEntry,
    coordinator: RecameraCoordinator,
) -> None:
    """Backfill hardware identity for upgraded entries and reject mismatch."""
    stored_mac = normalize_mac_address(config_entry.data.get(CONF_MAC_ADDRESS))
    try:
        discovered_mac = await coordinator.client.async_get_network_identity()
    except RecameraError as err:
        if stored_mac:
            raise ConfigEntryNotReady(
                "Unable to confirm the stored hardware identity"
            ) from err
        discovered_mac = None
    detected_mac = normalize_mac_address(discovered_mac)
    if stored_mac and detected_mac and stored_mac != detected_mac:
        raise ConfigEntryNotReady(
            "Authenticated device hardware identity does not match"
        )
    if stored_mac and detected_mac is None:
        raise ConfigEntryNotReady("Device did not expose its stored hardware identity")

    info = coordinator.data.info if coordinator.data else coordinator.client.info
    stored_serial = normalize_serial_number(config_entry.data.get(CONF_SERIAL_NUMBER))
    mac_matches = bool(stored_mac and detected_mac and stored_mac == detected_mac)
    if stored_serial:
        if info.serial_number:
            if stored_serial != info.serial_number:
                raise ConfigEntryNotReady(
                    "Authenticated device serial identity does not match"
                )
        elif not mac_matches:
            raise ConfigEntryNotReady(
                "Authenticated device MAC identity does not match"
            )
    if not stored_mac and not stored_serial and not detected_mac:
        raise ConfigEntryNotReady("Device did not expose a stable hardware identity")
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


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a reCamera Pro entry."""
    unloaded = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if unloaded:
        coordinator: RecameraCoordinator | None = getattr(
            config_entry, "runtime_data", None
        )
        if coordinator is not None:
            await coordinator.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Remove persisted dynamic entity metadata."""
    await async_remove_store(hass, config_entry.entry_id)
    await Store(
        hass,
        1,
        f"{DOMAIN}.capture.{config_entry.entry_id}",
    ).async_remove()


def _load_entity_translations(language: str) -> dict[str, Any]:
    """Load the integration entity translation table for one language."""
    filename = (
        "zh-Hans.json" if str(language or "").lower().startswith("zh") else "en.json"
    )
    path = Path(__file__).parent / "translations" / filename
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    entity_map = payload.get("entity")
    return entity_map if isinstance(entity_map, dict) else {}


def _resolve_visual_class_name(
    entry: er.RegistryEntry,
    coordinator: RecameraCoordinator,
) -> str | None:
    """Resolve the class_name placeholder for a visual_class binary sensor."""
    data = getattr(coordinator, "data", None)
    catalog = getattr(data, "class_catalog", None) or {}
    for item in catalog.values():
        if entry.unique_id == coordinator.class_entity_unique_id(item):
            return str(item.class_name)
    original = str(getattr(entry, "original_name", "") or "")
    match = re.fullmatch(
        r"(?:检测到\s+(.+)|(.+)\s+detected)",
        original,
    )
    if match:
        return match.group(1) or match.group(2)
    return None


async def _async_sync_entity_registry_names(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    coordinator: RecameraCoordinator,
) -> None:
    """Synchronize original_name in entity registry with active language."""
    try:
        registry = er.async_get(hass)
    except AttributeError, KeyError:
        return
    language = effective_integration_language(hass, config_entry)
    executor = getattr(hass, "async_add_executor_job", None)
    if executor is not None:
        entity_map = await executor(_load_entity_translations, language)
    else:
        entity_map = _load_entity_translations(language)
    if not entity_map:
        return
    for entry in list(registry.entities.values()):
        if (
            entry.platform != DOMAIN
            or entry.config_entry_id != config_entry.entry_id
            or getattr(entry, "name", None) is not None
        ):
            continue
        translation_key = getattr(entry, "translation_key", None)
        if not translation_key:
            continue
        domain_map = entity_map.get(entry.domain)
        if not isinstance(domain_map, dict):
            continue
        trans_entry = domain_map.get(translation_key)
        if not isinstance(trans_entry, dict):
            continue
        template = trans_entry.get("name")
        if not isinstance(template, str) or not template:
            continue
        if translation_key == "visual_class":
            class_name = _resolve_visual_class_name(entry, coordinator)
            if not class_name:
                continue
            target_name = template.replace("{class_name}", class_name)
        elif "{" in template:
            continue
        else:
            target_name = template
        if getattr(entry, "original_name", None) != target_name:
            registry.async_update_entity(
                entry.entity_id,
                original_name=target_name,
            )
