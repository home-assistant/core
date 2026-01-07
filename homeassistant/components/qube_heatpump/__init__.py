"""The Qube Heat Pump integration."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
import yaml

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.loader import async_get_integration, async_get_loaded_integration

from .const import (
    CONF_FILE_NAME,
    CONF_FRIENDLY_NAME_LANGUAGE,
    CONF_HOST,
    CONF_LABEL,
    CONF_PORT,
    CONF_SHOW_LABEL_IN_NAME,
    CONF_UNIT_ID,
    DEFAULT_FRIENDLY_NAME_LANGUAGE,
    DEFAULT_PORT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import QubeCoordinator
from .hub import EntityDef, QubeHub


@dataclass
class QubeData:
    """Runtime data for Qube Heat Pump."""

    hub: QubeHub
    coordinator: QubeCoordinator
    label: str | None
    apply_label_in_name: bool
    version: str
    multi_device: bool
    alarm_group_object_id: str
    friendly_name_language: str
    tariff_tracker: Any | None = None
    thermic_tariff_tracker: Any | None = None
    daily_tariff_tracker: Any | None = None
    daily_thermic_tariff_tracker: Any | None = None


type QubeConfigEntry = ConfigEntry[QubeData]

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML configuration from path."""
    with path.open("r", encoding="utf-8") as handle:
        return cast("dict[str, Any]", yaml.safe_load(handle))


def _slugify(text: str) -> str:
    """Make text safe for use as an ID."""
    return "".join(ch if ch.isalnum() else "_" for ch in str(text)).strip("_").lower()


def _unique_id_for(
    platform: str,
    item: dict[str, Any],
    vendor_id: str | None,
    entry_id: str,
    multi_device: bool,
) -> str:
    """Generate a stable unique ID for an entity."""
    suffix = entry_id
    if vendor_id:
        base = vendor_id.lower()
        return f"{base}_{suffix}" if multi_device else base
    input_type = str(item.get("input_type") or item.get("write_type") or "value")
    address = item.get("address")
    base = f"{platform}_{input_type}_{address}".lower()
    return f"{base}_{suffix}" if multi_device else base


def _to_entity_defs(
    platform: str,
    items: list[dict[str, Any]] | None,
    entry_id: str,
    multi_device: bool,
) -> list[EntityDef]:
    """Convert raw spec items into EntityDef objects."""
    entities: list[EntityDef] = []
    for item in items or []:
        try:
            address = int(item["address"])
        except (KeyError, TypeError, ValueError):
            continue
        vendor_id_raw = item.get("unique_id")
        vendor_id = str(vendor_id_raw).strip() if vendor_id_raw else None
        vendor_id_norm = vendor_id.lower() if vendor_id else None
        unique_id = _unique_id_for(
            platform, item, vendor_id_norm, entry_id, multi_device
        )

        display_name = item.get("name")
        if not display_name and vendor_id:
            display_name = vendor_id

        device_class = item.get("device_class")
        state_class = item.get("state_class")
        if isinstance(device_class, str) and device_class.lower() == "enum":
            state_class = None
        translation_key = item.get("translation_key")
        if not translation_key and vendor_id:
            translation_key = _slugify(vendor_id)

        entities.append(
            EntityDef(
                platform=platform,
                name=display_name,
                address=address,
                vendor_id=vendor_id_norm,
                input_type=item.get("input_type"),
                write_type=item.get("write_type"),
                data_type=item.get("data_type"),
                unit_of_measurement=item.get("unit_of_measurement"),
                device_class=device_class,
                state_class=state_class,
                precision=item.get("precision"),
                unique_id=unique_id,
                offset=item.get("offset"),
                scale=item.get("scale"),
                min_value=item.get("min_value"),
                translation_key=translation_key,
            )
        )
    return entities


def _suggest_object_id(
    ent: EntityDef,
    label: str | None,
    show_label_option: bool,
    multi_device: bool,
) -> str | None:
    """Suggest an entity ID slug."""
    base: str | None = ent.vendor_id or ent.unique_id
    if not base:
        return None
    base = base.lower()
    if base == "unitstatus":
        base = "qube_status_heatpump"

    apply_label = show_label_option or multi_device
    if apply_label and label and not base.startswith(f"{label}_"):
        base = f"{label}_{base}"
    return _slugify(base)


def _alarm_group_object_id(label: str | None, multi_device: bool) -> str:
    """Generate the object ID for the alarm group."""
    base = "qube_alarm_sensors"
    if multi_device and label:
        base = f"{base}_{label}"
    return base


def _resolve_entry(
    hass: HomeAssistant, entry_id: str | None, label_value: str | None
) -> ConfigEntry | None:
    """Resolve a config entry from ID or label."""
    if entry_id:
        return hass.config_entries.async_get_entry(entry_id)
    if label_value:
        for cfg in hass.config_entries.async_entries(DOMAIN):
            if not isinstance(cfg, ConfigEntry):
                continue
            # We can't strictly type check runtime_data here easily without casting,
            # but we know it's QubeData if loaded.
            try:
                data = cfg.runtime_data
                # runtime_data might not be loaded if entry is not setup
                if (
                    getattr(data, "label", None) == label_value
                    or getattr(data.hub, "label", None) == label_value
                ):
                    return cfg
            except AttributeError:
                continue
    loaded_entries = [
        cfg
        for cfg in hass.config_entries.async_entries(DOMAIN)
        if getattr(cfg, "runtime_data", None)
    ]
    if len(loaded_entries) == 1:
        return loaded_entries[0]
    return None


async def _service_reconfigure(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the reconfigure service."""
    data = vol.Schema({vol.Optional("entry_id"): str})(call.data)
    target_entry: ConfigEntry | None = None
    entry_id = data.get("entry_id")
    if entry_id:
        target_entry = hass.config_entries.async_get_entry(entry_id)
    else:
        entries = hass.config_entries.async_entries(DOMAIN)
        if len(entries) == 1:
            target_entry = entries[0]
    if not target_entry:
        _LOGGER.warning("Reconfigure: no entry resolved; pass entry_id")
        return
    try:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_RECONFIGURE,
                "entry_id": target_entry.entry_id,
            },
            data={"entry_id": target_entry.entry_id},
        )
    except HomeAssistantError as exc:
        _LOGGER.warning("Reconfigure flow not available: %s", exc)
    except Exception as exc:  # pylint: disable=broad-except  # noqa: BLE001
        _LOGGER.warning("Unexpected error in reconfigure flow: %s", exc)


WRITE_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Required("address"): vol.Coerce(int),
        vol.Required("value"): vol.Coerce(float),
        vol.Optional("data_type", default="uint16"): vol.In(
            {"uint16", "int16", "float32"}
        ),
        vol.Optional("entry_id"): str,
        vol.Optional("label"): str,
    }
)


async def _service_write_register(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the write_register service."""
    data = dict(call.data)
    data = WRITE_REGISTER_SCHEMA(data)
    target = _resolve_entry(hass, data.get("entry_id"), data.get("label"))
    if target is None:
        _LOGGER.error(
            "Write_register: unable to resolve integration entry; specify entry_id or label"
        )
        return
    target_data = target.runtime_data
    if not target_data:
        _LOGGER.error(
            "Write_register: integration entry %s is not loaded", target.entry_id
        )
        return
    hub_target = target_data.hub
    if hub_target is None:
        _LOGGER.error("Write_register: no hub available for entry %s", target.entry_id)
        return
    await hub_target.async_connect()
    data_type = str(data["data_type"]).lower()

    try:
        await hub_target.async_write_register(
            data["address"],
            data["value"],
            data_type,
        )
    except Exception:
        _LOGGER.exception("Write_register: failed to write address %s", data["address"])
        raise
    coordinator_target = target_data.coordinator
    if coordinator_target is not None:
        await coordinator_target.async_request_refresh()


async def async_setup_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> bool:  # noqa: C901
    """Set up Qube Heat Pump from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    yaml_path = Path(__file__).parent / CONF_FILE_NAME
    if not yaml_path.exists():
        yaml_path = Path(__file__).resolve().parents[2] / CONF_FILE_NAME

    raw_spec = await hass.async_add_executor_job(_load_yaml, yaml_path)
    spec = raw_spec[0] if isinstance(raw_spec, list) and raw_spec else raw_spec
    spec = dict(spec)
    spec["host"] = host
    spec["port"] = port
    options = dict(entry.options)
    options_changed = False

    unit_id = int(options.get(CONF_UNIT_ID, spec.get("unit_id", 1)))

    existing_entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != entry.entry_id
    ]
    multi_device = len(existing_entries) >= 1

    label = options.get(CONF_LABEL)
    if not label:
        used_labels = {
            e.options.get(CONF_LABEL)
            for e in existing_entries
            if e.options.get(CONF_LABEL)
        }
        # Fallback to generating a label if none provided
        for i in range(1, 100):
            candidate = f"qube{i}"
            if candidate not in used_labels:
                label = candidate
                break

    show_label_option = bool(options.get(CONF_SHOW_LABEL_IN_NAME, False))
    if multi_device and not show_label_option:
        options[CONF_SHOW_LABEL_IN_NAME] = True
        show_label_option = True
        options_changed = True

    if options_changed:
        hass.config_entries.async_update_entry(entry, options=options)

    # Rename existing entries from "WP Qube" to "Qube Heat Pump"
    if entry.title.startswith("WP Qube"):
        new_title = entry.title.replace("WP Qube", "Qube Heat Pump")
        hass.config_entries.async_update_entry(entry, title=new_title)

    hub = QubeHub(hass, host, port, entry.entry_id, unit_id, label)

    # Load fallback translations (manual resolution to avoid device prefix)
    translations_path = Path(__file__).parent / "translations" / "en.json"
    if translations_path.exists():

        def _load_translations() -> dict[str, Any]:
            with translations_path.open("r", encoding="utf-8") as f:
                return cast("dict[str, Any]", json.load(f))

        with contextlib.suppress(OSError, ValueError):
            translations = await hass.async_add_executor_job(_load_translations)
            hub.set_translations(translations)

    await hub.async_resolve_ip()

    # Populate hub entities
    hub.entities.extend(
        _to_entity_defs("sensor", spec.get("sensors"), entry.entry_id, multi_device)
    )

    ent_reg = er.async_get(hass)

    for ent in hub.entities:
        if not ent.unique_id:
            continue
        domain = ent.platform
        slug = _suggest_object_id(ent, label, show_label_option, multi_device)
        try:
            registry_entry = ent_reg.async_get_or_create(
                domain,
                DOMAIN,
                ent.unique_id,
                config_entry=entry,
                suggested_object_id=slug,
            )
        except Exception:  # noqa: BLE001
            # If entity creation fails, skip it
            continue
        if slug:
            desired_eid = f"{domain}.{slug}"
            if (
                registry_entry.entity_id != desired_eid
                and ent_reg.async_get(desired_eid) is None
            ):
                with contextlib.suppress(Exception):
                    ent_reg.async_update_entity(
                        registry_entry.entity_id, new_entity_id=desired_eid
                    )

    version = "unknown"
    with contextlib.suppress(Exception):
        integration = async_get_loaded_integration(hass, DOMAIN)
        if not integration:
            integration = await async_get_integration(hass, DOMAIN)
        if integration and getattr(integration, "version", None):
            version = str(integration.version)

    if multi_device:
        for other_entry in existing_entries:
            if not bool(other_entry.options.get(CONF_SHOW_LABEL_IN_NAME, False)):
                other_updated = dict(other_entry.options)
                other_updated[CONF_SHOW_LABEL_IN_NAME] = True
                hass.config_entries.async_update_entry(
                    other_entry, options=other_updated
                )

    apply_label_in_name = show_label_option or multi_device

    async def _options_updated(hass: HomeAssistant, updated_entry: ConfigEntry) -> None:
        """Handle options update."""
        if updated_entry.entry_id != entry.entry_id:
            return
        # Avoid reloading if we are currently in the process of setting up
        if updated_entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_options_updated))

    coordinator = QubeCoordinator(hass, hub, entry)

    alarm_group_object_id = _alarm_group_object_id(label, multi_device)

    entry.runtime_data = QubeData(
        hub=hub,
        coordinator=coordinator,
        label=label,
        apply_label_in_name=apply_label_in_name,
        version=version,
        multi_device=multi_device,
        alarm_group_object_id=alarm_group_object_id,
        friendly_name_language=options.get(
            CONF_FRIENDLY_NAME_LANGUAGE, DEFAULT_FRIENDLY_NAME_LANGUAGE
        ),
    )

    with contextlib.suppress(Exception):
        ir.async_delete_issue(hass, DOMAIN, "registry_migration_suggested")

    for other in existing_entries:
        if (
            other.state is ConfigEntryState.LOADED
            and hasattr(other, "runtime_data")
            and not other.runtime_data.multi_device
        ):
            hass.async_create_task(hass.config_entries.async_reload(other.entry_id))

    if not hass.services.has_service(DOMAIN, "reconfigure"):

        async def _reconfigure_wrapper(call: ServiceCall) -> None:
            await _service_reconfigure(hass, call)

        hass.services.async_register(
            DOMAIN,
            "reconfigure",
            _reconfigure_wrapper,
            schema=vol.Schema({vol.Optional("entry_id"): str}),
        )

    if not hass.services.has_service(DOMAIN, "write_register"):

        async def _write_register_wrapper(call: ServiceCall) -> None:
            await _service_write_register(hass, call)

        hass.services.async_register(
            DOMAIN,
            "write_register",
            _write_register_wrapper,
            schema=WRITE_REGISTER_SCHEMA,
        )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Use contextlib.suppress to safely handle cleanup even if setup failed
    with contextlib.suppress(AttributeError):
        if hub := entry.runtime_data.hub:
            await hub.async_close()

    with contextlib.suppress(AttributeError):
        if object_id := entry.runtime_data.alarm_group_object_id:
            with contextlib.suppress(Exception):
                await hass.services.async_call(
                    "group",
                    "remove",
                    {"object_id": object_id},
                    blocking=True,
                )

    return bool(unload_ok)
