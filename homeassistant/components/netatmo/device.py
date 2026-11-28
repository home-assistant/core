"""Device registry helpers for the Netatmo integration."""

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING

import pyatmo
from pyatmo.modules.device_types import DEVICE_DESCRIPTION_MAP

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .const import CONF_URL_CONTROL, DOMAIN, MANUFACTURER

if TYPE_CHECKING:
    from .coordinator import NetatmoConfigEntry

SCHEDULE_SELECT_SUFFIX = "-schedule-select"


def legacy_climate_issue_id(home_id: str) -> str:
    """Return the repair issue id for a home disabled through its old device."""
    return f"legacy_climate_device_disabled_{home_id}"


def _bridged_children(home: pyatmo.Home) -> Iterator[tuple[str, str]]:
    """Yield (module id, parent id) for every child a module lists as bridged."""
    return (
        (child_id, module.entity_id)
        for module in home.modules.values()
        for child_id in module.modules or ()
        if child_id in home.modules and child_id != module.entity_id
    )


def _declared_bridges(home: pyatmo.Home) -> Iterator[tuple[str, str]]:
    """Yield (module id, parent id) for every module that names its bridge."""
    return (
        (module.entity_id, bridge)
        for module in home.modules.values()
        if (bridge := module.bridge)
        and bridge in home.modules
        and bridge != module.entity_id
    )


def netatmo_module_parents(account: pyatmo.AsyncAccount) -> dict[str, str]:
    """Map each module id to the id of the module it reports through.

    The API records the relationship from both ends and neither end is
    complete: a station lists bridged children that never name it back, and a
    module can name a bridge that does not list it. `bridge` is single-valued,
    so it wins wherever the two disagree.
    """
    parents: dict[str, str] = {}
    for home in account.homes.values():
        for child_id, parent_id in _bridged_children(home):
            parents.setdefault(child_id, parent_id)
        parents.update(_declared_bridges(home))

    return parents


def _register_bridge(
    device_registry: dr.DeviceRegistry,
    entry: NetatmoConfigEntry,
    home: pyatmo.Home,
    module_id: str,
    module_parents: dict[str, str],
    parent_device_ids: dict[str, str],
    seen: set[str],
) -> str:
    """Register a bridging module after its own bridge and return its device id."""
    if (device_id := parent_device_ids.get(module_id)) is not None:
        return device_id

    seen.add(module_id)
    via_device_id = parent_device_ids[home.entity_id]
    parent_id = module_parents.get(module_id)
    # `seen` bounds the walk; a cycle in unvalidated API data would not terminate
    if parent_id is not None and parent_id not in seen:
        via_device_id = _register_bridge(
            device_registry,
            entry,
            home,
            parent_id,
            module_parents,
            parent_device_ids,
            seen,
        )

    module = home.modules[module_id]
    manufacturer, model = DEVICE_DESCRIPTION_MAP.get(
        module.device_type, (MANUFACTURER, module.device_type.value)
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, module_id)},
        manufacturer=manufacturer,
        model=model,
        name=module.name,
        via_device_id=via_device_id,
    )
    parent_device_ids[module_id] = device_entry.id
    return device_entry.id


@callback
def async_disabled_netatmo_ids(
    hass: HomeAssistant, entry: NetatmoConfigEntry
) -> list[str]:
    """Return the Netatmo ids of every disabled device.

    A superset of the disabled home ids. Module ids never match a home id, so
    passing them through to pyatmo's denylist is harmless and avoids having to
    know which devices are homes before the topology has been fetched.
    """
    return [
        identifier[1]
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        )
        if device.disabled_by
        for identifier in device.identifiers
        if identifier[0] == DOMAIN
    ]


@callback
def async_register_parent_devices(
    hass: HomeAssistant,
    entry: NetatmoConfigEntry,
    account: pyatmo.AsyncAccount,
    module_parents: dict[str, str],
) -> dict[str, str]:
    """Register a device per home and per bridging module.

    Maps Netatmo ids to device registry ids.
    """
    device_registry = dr.async_get(hass)
    parent_device_ids: dict[str, str] = {}

    for home_id, home_name in account.all_home_names.items():
        device_entry = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, home_id)},
            manufacturer=MANUFACTURER,
            model="Home",
            name=home_name,
            configuration_url=CONF_URL_CONTROL,
        )
        parent_device_ids[home_id] = device_entry.id

    for home in account.homes.values():
        bridges = {
            module_parents[module_id]
            for module_id in home.modules
            if module_id in module_parents
        }
        for module_id in home.modules:
            if module_id in bridges:
                _register_bridge(
                    device_registry,
                    entry,
                    home,
                    module_id,
                    module_parents,
                    parent_device_ids,
                    set(),
                )

    return parent_device_ids


@callback
def async_sync_home_disabled_state(
    hass: HomeAssistant, entry: NetatmoConfigEntry, home_device_ids: Iterable[str]
) -> None:
    """Mirror each home device's disabled state onto its descendants.

    Devices disabled by the user are left alone in both directions, so toggling a
    home never undoes a manual choice.
    """
    device_registry = dr.async_get(hass)

    children: dict[str, list[dr.DeviceEntry]] = {}
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if device.via_device_id:
            children.setdefault(device.via_device_id, []).append(device)

    for home_device_id in home_device_ids:
        home_device = device_registry.async_get(home_device_id)
        assert home_device

        disabled = home_device.disabled_by is not None
        # Walk the whole subtree; a module can be a grandchild via its gateway
        stack = list(children.get(home_device_id, []))
        while stack:
            device = stack.pop()
            stack.extend(children.get(device.id, []))

            if disabled and device.disabled_by is None:
                device_registry.async_update_device(
                    device.id, disabled_by=dr.DeviceEntryDisabler.INTEGRATION
                )
            elif (
                not disabled
                and device.disabled_by is dr.DeviceEntryDisabler.INTEGRATION
            ):
                device_registry.async_update_device(device.id, disabled_by=None)


@callback
def async_hide_schedule_select_instead(
    hass: HomeAssistant, device_id: str, entity_id: str | None
) -> None:
    """Enable a home device, hiding only the schedule select that sat on it."""
    # Before the device: enabling it re-enables what its disable cascaded to
    if entity_id is not None:
        er.async_get(hass).async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.USER
        )
    dr.async_get(hass).async_update_device(device_id, disabled_by=None)


@callback
def async_migrate_legacy_climate_devices(
    hass: HomeAssistant, entry: NetatmoConfigEntry
) -> None:
    """Undo home disables that only meant to hide the schedule select.

    Up to 2026.8 the schedule select sat alone on a "Climate" device with the
    home id, so disabling it hid just the select. That device is the home now,
    and disabling it drops the whole home. 2026.9 already renamed the model of
    devices it set up, which makes those indistinguishable from a deliberate
    home disable, so they get a repair instead.
    """
    device_registry = dr.async_get(hass)
    for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        if entity.domain != Platform.SELECT or not entity.unique_id.endswith(
            SCHEDULE_SELECT_SUFFIX
        ):
            continue

        home_id = entity.unique_id.removesuffix(SCHEDULE_SELECT_SUFFIX)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, home_id), entry.entry_id
        )
        if device is None or device.disabled_by is not dr.DeviceEntryDisabler.USER:
            continue

        if device.model == "Climate":
            async_hide_schedule_select_instead(hass, device.id, entity.entity_id)
            continue

        ir.async_create_issue(
            hass,
            DOMAIN,
            legacy_climate_issue_id(home_id),
            config_entry_id=entry.entry_id,
            data={"device_id": device.id, "entity_id": entity.id},
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="legacy_climate_device_disabled",
            translation_placeholders={
                "home_name": device.name_by_user or device.name or ""
            },
        )
