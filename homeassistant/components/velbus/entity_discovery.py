"""Discover Velbus entities from the live bus state."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from velbusaio.controller import Velbus

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

if TYPE_CHECKING:
    from . import VelbusConfigEntry


def entity_registry_key(domain: str, unique_id: str) -> str:
    """Return a domain-scoped key for tracking known unique IDs."""
    return f"{domain}:{unique_id}"


def discover_binary_sensor_entities(controller: Velbus) -> list[Entity]:
    """Return binary sensor entities for the current bus state."""
    from .binary_sensor import VelbusBinarySensor  # noqa: PLC0415

    return [
        VelbusBinarySensor(channel) for channel in controller.get_all_binary_sensor()
    ]


def discover_button_entities(controller: Velbus) -> list[Entity]:
    """Return button entities for the current bus state."""
    from .button import VelbusButton  # noqa: PLC0415

    return [VelbusButton(channel) for channel in controller.get_all_button()]


def discover_climate_entities(controller: Velbus) -> list[Entity]:
    """Return climate entities for the current bus state."""
    from .climate import VelbusClimate  # noqa: PLC0415

    return [VelbusClimate(channel) for channel in controller.get_all_climate()]


def discover_cover_entities(controller: Velbus) -> list[Entity]:
    """Return cover entities for the current bus state."""
    from .cover import VelbusCover  # noqa: PLC0415

    return [VelbusCover(channel) for channel in controller.get_all_cover()]


def discover_event_entities(controller: Velbus) -> list[Entity]:
    """Return event entities for the current bus state."""
    from .event import VelbusButtonEvent  # noqa: PLC0415

    return [VelbusButtonEvent(channel) for channel in controller.get_all_button()]


def discover_light_entities(controller: Velbus) -> list[Entity]:
    """Return light entities for the current bus state."""
    from .light import VelbusButtonLight, VelbusLight  # noqa: PLC0415

    entities: list[Entity] = [
        VelbusLight(channel) for channel in controller.get_all_light()
    ]
    entities.extend(VelbusButtonLight(channel) for channel in controller.get_all_led())
    return entities


def discover_select_entities(controller: Velbus) -> list[Entity]:
    """Return select entities for the current bus state."""
    from .select import VelbusSelect  # noqa: PLC0415

    return [VelbusSelect(channel) for channel in controller.get_all_select()]


def discover_sensor_entities(controller: Velbus) -> list[Entity]:
    """Return sensor entities for the current bus state."""
    from .sensor import COUNTER_SENSOR_KEYS, SENSOR_DESCRIPTIONS, VelbusSensor  # noqa: PLC0415

    entities: list[Entity] = []
    for channel in controller.get_all_sensor():
        entities.extend(
            VelbusSensor(
                channel,
                SENSOR_DESCRIPTIONS[sensor_type],
                is_counter=sensor_type in COUNTER_SENSOR_KEYS,
            )
            for sensor_type in channel.get_sensor_types()
        )

    return entities


def discover_switch_entities(controller: Velbus) -> list[Entity]:
    """Return switch entities for the current bus state."""
    from .switch import VelbusSwitch  # noqa: PLC0415

    return [VelbusSwitch(channel) for channel in controller.get_all_switch()]


async def async_setup_platform_discovery(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discover: Callable[[Velbus], list[Entity]],
    platform_domain: str,
) -> None:
    """Wait for the initial scan and register ongoing entity discovery."""
    await entry.runtime_data.scan_task

    @callback
    def _add_discovered() -> None:
        entities = discover(entry.runtime_data.controller)
        new_entities = [
            entity
            for entity in entities
            if entity.unique_id
            and entity_registry_key(platform_domain, entity.unique_id)
            not in entry.runtime_data.known_unique_ids
        ]
        if not new_entities:
            return
        entry.runtime_data.known_unique_ids.update(
            entity_registry_key(platform_domain, unique_id)
            for entity in new_entities
            if (unique_id := entity.unique_id)
        )
        async_add_entities(new_entities)

    entry.runtime_data.discoverers.append(_add_discovered)
    _add_discovered()
