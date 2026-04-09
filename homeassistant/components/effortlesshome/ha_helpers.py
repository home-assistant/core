"""Collection of utility methods for dealing with HomeAssistant."""

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry


def get_all_entities(
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    area_id: str,
    domains: list[str] | None = None,
) -> list[RegistryEntry]:
    """Return all entities from an area."""
    entities: list[RegistryEntry] = []

    for _entity_id, entity in entity_registry.entities.items():
        if get_area_id(entity, device_registry) != area_id:
            continue

        if domains is None or entity.domain not in domains:
            continue

        entities.append(entity)

    return entities


def get_area_id(entity: RegistryEntry, device_registry: DeviceRegistry) -> str | None:
    """Get area_id from a registry entry."""

    # Defined directly at entity
    if entity.area_id is not None:
        return entity.area_id

    # Inherited from device
    if entity.device_id is not None:
        device = device_registry.devices.get(entity.device_id)
        if device is not None:
            return device.area_id

    return None


def all_states_are_off(
    hass: HomeAssistant,
    presence_indicating_entity_ids: list[str],
    on_states: list[str],
) -> bool:
    """Make sure that none of the entities is in any on state."""
    all_states = [
        hass.states.get(entity_id) for entity_id in presence_indicating_entity_ids
    ]
    return all(state.state not in on_states for state in filter(None, all_states))


def is_valid_entity(hass: HomeAssistant, entity: RegistryEntry) -> bool:
    """Check whether an entity should be included."""
    if entity.disabled:
        return False

    entity_state = hass.states.get(entity.entity_id)
    if entity_state and entity_state.state == STATE_UNAVAILABLE:
        return False

    return True


def friendly_name_for_entity_id(entity_id: str, hass: HomeAssistant):
    """Helper to get friendly name for entity."""
    state = hass.states.get(entity_id)
    if state and state.attributes.get("friendly_name"):
        return state.attributes["friendly_name"]

    return entity_id