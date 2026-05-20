"""Matter device access helpers for Connectivity Monitor."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

_LOGGER = logging.getLogger(__name__)

MATTER_DOMAIN = "matter"


async def async_get_matter_devices(hass: HomeAssistant) -> list[dict]:
    """Return a list of all Matter devices from the HA device registry.

    Matter devices are identified by the 'matter' domain in the device registry.
    The node_id stored is the full identifier string (e.g. '1-5' meaning
    matter server instance 1, node 5).
    """
    devices: list[dict] = []
    try:
        device_registry = dr.async_get(hass)
        for device_entry in device_registry.devices.values():
            for identifier in device_entry.identifiers:
                if identifier[0] == MATTER_DOMAIN:
                    node_id = str(identifier[1])
                    devices.append(
                        {
                            "node_id": node_id,
                            "name": (
                                device_entry.name_by_user
                                or device_entry.name
                                or node_id
                            ),
                            "model": device_entry.model,
                            "manufacturer": device_entry.manufacturer,
                            "device_id": device_entry.id,
                        }
                    )
                    break
    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning(
            "Could not enumerate Matter devices from device registry: %s", err
        )

    _LOGGER.debug("Matter devices found: %d", len(devices))
    return devices


async def async_get_matter_device_active(
    hass: HomeAssistant, node_id: str
) -> bool | None:
    """Return True if the Matter device has at least one available entity.

    A Matter device is considered Active when one or more of its entities
    report a state other than 'unavailable'.  Returns None when the device
    cannot be found at all.
    """
    try:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)

        # Locate the device entry for this node_id
        device_entry = None
        for de in device_registry.devices.values():
            for identifier in de.identifiers:
                if identifier[0] == MATTER_DOMAIN and str(identifier[1]) == node_id:
                    device_entry = de
                    break
            if device_entry is not None:
                break

        if device_entry is None:
            _LOGGER.debug("Matter device not found for node_id '%s'", node_id)
            return None

        # Gather all non-disabled entities belonging to this device
        # that were created by the Matter integration itself.
        # Entities from other integrations (e.g. our own MatterSensor) are
        # excluded because their state is never "unavailable" and would cause
        # a false-Active result.
        entities = [
            e
            for e in entity_registry.entities.values()
            if e.device_id == device_entry.id
            and not e.disabled
            and e.platform == MATTER_DOMAIN
        ]

        if not entities:
            _LOGGER.debug("No enabled entities found for Matter device '%s'", node_id)
            return None

        # Device is active when any entity is in a non-unavailable state
        for entity_entry in entities:
            state = hass.states.get(entity_entry.entity_id)
            if state is not None and state.state != "unavailable":
                return True

    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning(
            "Failed to determine active state for Matter device '%s': %s",
            node_id,
            err,
        )
        return None
    else:
        return False
