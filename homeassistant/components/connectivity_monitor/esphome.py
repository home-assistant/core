"""ESPHome device access helpers for Connectivity Monitor."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

_LOGGER = logging.getLogger(__name__)

ESPHOME_DOMAIN = "esphome"


async def async_get_esphome_devices(hass: HomeAssistant) -> list[dict]:
    """Return a list of all ESPHome devices discovered in Home Assistant.

    Primary path: iterate loaded ESPHome config entries (one per node) and
    find the device registry entry associated with each.  This is the most
    reliable method because each ESPHome node has exactly one config entry.

    Fallback: scan the device registry for any device whose identifiers
    contain the 'esphome' domain (older HA / edge-case layout).

    The stable key stored as device_id is the config-entry entry_id so it
    survives device renames.
    """
    # pylint: disable=too-many-nested-blocks
    devices: list[dict] = []
    seen_device_registry_ids: set[str] = set()

    try:
        device_registry = dr.async_get(hass)

        # ── Primary path: one config entry per ESPHome node ───────────────────
        for entry in hass.config_entries.async_entries(ESPHOME_DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue

            # Find the device that lists this config entry
            device_entry = None
            for de in device_registry.devices.values():
                if entry.entry_id in de.config_entries:
                    # Prefer the device that also has an 'esphome' identifier
                    # when there are sub-devices (e.g. multi-device firmware).
                    has_esphome_id = any(
                        idf[0] == ESPHOME_DOMAIN for idf in de.identifiers
                    )
                    if has_esphome_id or device_entry is None:
                        device_entry = de
                    if has_esphome_id:
                        break

            if device_entry is None:
                _LOGGER.debug(
                    "ESPHome config entry '%s' (%s) has no associated device yet",
                    entry.title,
                    entry.entry_id,
                )
                continue

            if device_entry.id in seen_device_registry_ids:
                continue
            seen_device_registry_ids.add(device_entry.id)

            # Extract the real ESPHome identifier (e.g. MAC-based) so the sensor
            # can attach to the existing device rather than create a new one.
            esphome_identifier = (
                next(
                    (
                        str(idf[1])
                        for idf in device_entry.identifiers
                        if idf[0] == ESPHOME_DOMAIN
                    ),
                    None,
                )
                or entry.unique_id
            )  # entry.unique_id is the MAC for ESPHome config entries

            # Also grab the MAC from connections — used as a reliable fallback
            # in DeviceInfo so HA can always match the existing ESPHome device.
            mac_address = next(
                (str(con[1]) for con in device_entry.connections if con[0] == "mac"),
                None,
            )

            # Use entry_id as the stable device_id key
            device_id = entry.entry_id
            devices.append(
                {
                    "device_id": device_id,
                    "entry_id": entry.entry_id,
                    "esphome_identifier": esphome_identifier,
                    "esphome_mac": mac_address,
                    "name": (
                        device_entry.name_by_user
                        or device_entry.name
                        or entry.title
                        or device_id
                    ),
                    "model": device_entry.model,
                    "manufacturer": device_entry.manufacturer,
                    "sw_version": device_entry.sw_version,
                }
            )

        # ── Fallback: identifier-based scan (catches older HA layouts) ────────
        if not devices:
            _LOGGER.debug(
                "ESPHome config-entry scan found 0 devices — falling back to "
                "device-registry identifier scan"
            )
            for device_entry in device_registry.devices.values():
                for identifier in device_entry.identifiers:
                    if identifier[0] == ESPHOME_DOMAIN:
                        if device_entry.id in seen_device_registry_ids:
                            break
                        seen_device_registry_ids.add(device_entry.id)
                        device_id = str(identifier[1])
                        mac_address = next(
                            (
                                str(con[1])
                                for con in device_entry.connections
                                if con[0] == "mac"
                            ),
                            None,
                        )
                        devices.append(
                            {
                                "device_id": device_id,
                                "entry_id": None,
                                "esphome_identifier": device_id,
                                "esphome_mac": mac_address,
                                "name": (
                                    device_entry.name_by_user
                                    or device_entry.name
                                    or device_id
                                ),
                                "model": device_entry.model,
                                "manufacturer": device_entry.manufacturer,
                                "sw_version": device_entry.sw_version,
                            }
                        )
                        break

    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning("Could not enumerate ESPHome devices: %s", err)

    _LOGGER.debug("ESPHome devices found: %d", len(devices))
    return devices


async def async_get_esphome_device_active(
    hass: HomeAssistant, device_id: str
) -> bool | None:
    """Return True if the ESPHome device has at least one available entity.

    A device is considered Active when one or more of its entities report a
    state other than 'unavailable'.  Returns None when the device cannot be
    found at all.

    device_id is either a config-entry entry_id (primary) or an identifier
    value (fallback).
    """
    try:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)

        # ── Primary: look up by config-entry entry_id ─────────────────────────
        device_entry = None
        entry = hass.config_entries.async_get_entry(device_id)
        if entry is not None and entry.domain == ESPHOME_DOMAIN:
            for de in device_registry.devices.values():
                if entry.entry_id in de.config_entries:
                    has_esphome_id = any(
                        idf[0] == ESPHOME_DOMAIN for idf in de.identifiers
                    )
                    if has_esphome_id or device_entry is None:
                        device_entry = de
                    if has_esphome_id:
                        break

        # ── Fallback: identifier-based lookup ─────────────────────────────────
        if device_entry is None:
            for de in device_registry.devices.values():
                for identifier in de.identifiers:
                    if (
                        identifier[0] == ESPHOME_DOMAIN
                        and str(identifier[1]) == device_id
                    ):
                        device_entry = de
                        break
                if device_entry is not None:
                    break

        if device_entry is None:
            _LOGGER.debug("ESPHome device not found for device_id '%s'", device_id)
            return None

        # Gather all non-disabled entities belonging to the ESPHome integration.
        # Entities from other integrations (e.g. our own ESPHomeSensor) are
        # excluded so they don't cause a false-Active result.
        entities = [
            e
            for e in entity_registry.entities.values()
            if e.device_id == device_entry.id
            and not e.disabled
            and e.platform == ESPHOME_DOMAIN
        ]

        if not entities:
            _LOGGER.debug(
                "No enabled ESPHome entities found for device '%s'", device_id
            )
            return None

        # Device is active when any entity is in a non-unavailable state
        for entity_entry in entities:
            state = hass.states.get(entity_entry.entity_id)
            if state is not None and state.state != "unavailable":
                return True

    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning(
            "Failed to determine active state for ESPHome device '%s': %s",
            device_id,
            err,
        )
        return None
    else:
        return False
