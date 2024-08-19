"""Automatic dashboarding facilities."""

from collections import defaultdict
import string
import typing

from blebox_uniapi.box import Box
import stringcase

from homeassistant.components import lovelace, sensor
from homeassistant.components.lovelace import dashboard
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import DOMAIN

if typing.TYPE_CHECKING:
    from .sensor import BleBoxSensorEntity


async def async_create_smart_meter_dashboards(
    call: ServiceCall,
    /,
    hass: HomeAssistant,
):
    """Automatically create dashboards for all smartMeter devices."""
    registry = er.async_get(hass)

    config_entry: ConfigEntry
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        product_map = hass.data[DOMAIN].get(config_entry.entry_id, {})
        product = product_map.get("product")

        if not product or not _is_smartmeter(product):
            continue

        entities = registry.entities.get_entries_for_config_entry_id(
            config_entry.entry_id
        )
        await async_dashboard_for_smartmeter_product(hass, config_entry, entities)


async def async_dashboard_for_smartmeter_product(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    registry_entries: list[RegistryEntry],
):
    """Create or update built-in smartMeter dashboard for single smartMeter product."""
    dashboards_collection: dashboard.DashboardsCollection
    dashboard_store: dashboard.LovelaceStorage

    dashboards_collection = hass.data[lovelace.DOMAIN]["dashboards_collection"]
    url = f"blebox.energy-dashboard.{config_entry.entry_id}"

    if url not in hass.data[lovelace.DOMAIN]["dashboards"]:
        await dashboards_collection.async_create_item(
            {
                lovelace.CONF_ALLOW_SINGLE_WORD: True,
                lovelace.CONF_URL_PATH: url,
                lovelace.CONF_TITLE: config_entry.title,
            }
        )

    dashboard_store = hass.data[lovelace.DOMAIN]["dashboards"][url]
    await dashboard_store.async_save(
        smartmeter_dashboard_config(hass, registry_entries)
    )


def smartmeter_dashboard_config(
    hass: HomeAssistant, registry_entries: list[RegistryEntry]
):
    """Create multi-tab smartMeter dashboard configuration."""
    # avoid circular imports
    from .sensor import BleBoxSensorEntity  # pylint: disable=import-outside-toplevel

    sensor_component: EntityComponent[sensor.SensorEntity] = hass.data[sensor.DOMAIN]

    by_phase = defaultdict(list)
    for entry in registry_entries:
        entity = sensor_component.get_entity(entry.entity_id)

        if not isinstance(entity, BleBoxSensorEntity):
            continue

        by_phase[f"{entity.probe_id+1}"].append(entity)

    views = [
        {
            "title": f"All phases ({' / '.join(by_phase.keys())})",
            "cards": [
                smartmeter_phase_card(phase, entities)
                for phase, entities in by_phase.items()
            ],
        }
    ]

    for phase, entities in by_phase.items():
        views.append(smartmeter_phase_view(phase, entities))

    return {"views": views}


def smartmeter_phase_card(phase: str, entities: list["BleBoxSensorEntity"]) -> dict:
    """Create dashboard card definition for single-phase smartMeter sensors.

    Such cards are to be included in main (all phases) dashboard view.
    """
    return {
        "title": f"Phase {phase}",
        "show_name": True,
        "show_icon": True,
        "show_state": True,
        "type": "glance",
        "columns": 1,
        "entities": [
            {"entity": e.entity_id, "name": humanize_alias(e.alias)} for e in entities
        ],
    }


def smartmeter_phase_view(phase: str, entities: list["BleBoxSensorEntity"]) -> dict:
    """Create dashboard view definition for single phase sensors view."""
    return {
        "title": f"Phase {phase}",
        "badges": [
            {
                "name": humanize_alias(entity.alias),
                "type": "entity",
                "entity": entity.entity_id,
                "state_content": ["name", "state"],
            }
            for entity in entities
            if "energy" in entity.alias.lower()
        ],
        "cards": [
            {
                "graph": "line",
                "name": humanize_alias(entity.alias),
                "type": "sensor",
                "entity": entity.entity_id,
                "detail": 1,
            }
            for entity in entities
        ],
    }


def _is_smartmeter(product: Box):
    """Heuristically tell whether given BleBox product represents smartMeter device."""
    return product.type == "multiSensor" and any(
        f.device_class == "apparentPower" for f in product.features.get("sensors", [])
    )


def humanize_alias(alias: str) -> str:
    """Convert blebox feature alias to human readable label."""
    return stringcase.sentencecase(alias.strip(string.digits))
