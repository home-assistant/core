"""The victron_gx integration."""

import logging

from homeassistant.components.automation import (
    DOMAIN as AUTOMATION_DOMAIN,
    automations_with_entity,
)
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN, scripts_with_entity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
    start,
)

from .const import DOMAIN
from .hub import Hub, VictronGxConfigEntry

_LOGGER = logging.getLogger(__name__)

_LEGACY_EVCHARGER_SENSOR_SUFFIXES = (
    "_evcharger_max_set_current",
    "_evcharger_min_set_current",
)
_LEGACY_SENSOR_BREAKS_IN_VERSION = "2027.2.0"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


def _automations_and_scripts_using_entity(
    hass: HomeAssistant, entity_id: str
) -> list[str]:
    """Return links to automations and scripts referencing an entity."""
    entity_registry = er.async_get(hass)
    items: list[str] = []
    for domain, entity_ids in (
        (AUTOMATION_DOMAIN, automations_with_entity(hass, entity_id)),
        (SCRIPT_DOMAIN, scripts_with_entity(hass, entity_id)),
    ):
        for used_entity_id in entity_ids:
            if entry := entity_registry.async_get(used_entity_id):
                items.append(
                    f"- [{entry.original_name or used_entity_id}]"
                    f"(/config/{domain}/edit/{entry.unique_id})"
                )
            else:
                items.append(f"- `{used_entity_id}`")
    return items


def _async_check_legacy_sensors(
    hass: HomeAssistant, config_entry: VictronGxConfigEntry
) -> None:
    """Create repairs for legacy sensors and remove them once disabled."""
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if (
            entity_entry.domain != Platform.SENSOR
            or not entity_entry.unique_id.endswith(_LEGACY_EVCHARGER_SENSOR_SUFFIXES)
        ):
            continue

        issue_id = f"deprecated_sensor_{entity_entry.unique_id}"
        if entity_entry.disabled:
            entity_registry.async_remove(entity_entry.entity_id)
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue

        items = _automations_and_scripts_using_entity(hass, entity_entry.entity_id)
        translation_key = "deprecated_sensor"
        placeholders = {"entity_id": entity_entry.entity_id}
        if items:
            translation_key = "deprecated_sensor_in_use"
            placeholders["items"] = "\n".join(items)

        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version=_LEGACY_SENSOR_BREAKS_IN_VERSION,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )


async def async_setup_entry(hass: HomeAssistant, entry: VictronGxConfigEntry) -> bool:
    """Set up victron_gx from a config entry."""
    _LOGGER.debug("async_setup_entry called for entry: %s", entry.entry_id)

    @callback
    def _async_check_legacy_sensors_at_start(_: HomeAssistant) -> None:
        _async_check_legacy_sensors(hass, entry)

    entry.async_on_unload(
        start.async_at_started(hass, _async_check_legacy_sensors_at_start)
    )

    hub = Hub(hass, entry)
    entry.runtime_data = hub

    # All platforms should be set up before starting the hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    try:
        await hub.start()
    except Exception as err:
        _LOGGER.error(
            "Error starting hub for entry %s: %s",
            entry.entry_id,
            err,
            exc_info=err,
        )
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        hub.unregister_all_new_metric_callbacks()
        raise

    async def _async_stop(_: Event) -> None:
        await hub.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )

    _LOGGER.debug("async_setup_entry completed for entry: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VictronGxConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry called for entry: %s", entry.entry_id)
    hub = entry.runtime_data
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hub.stop()
        hub.unregister_all_new_metric_callbacks()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Remove a device from the config entry if the device is no longer known."""
    hub: Hub = config_entry.runtime_data
    return not hub.is_device_connected(device_entry.identifiers)
