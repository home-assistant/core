"""The Airtouch 5 integration."""

import logging

from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient, AirtouchDevice
from airtouch5py.discovery import AirtouchDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.COVER]

_LOGGER = logging.getLogger(__name__)

type Airtouch5ConfigEntry = ConfigEntry[Airtouch5SimpleClient]


async def async_setup_entry(hass: HomeAssistant, entry: Airtouch5ConfigEntry) -> bool:
    """Set up Airtouch 5 from a config entry."""

    # Create API instance
    host = entry.data[CONF_HOST]

    # So for any device that is created using the old flow (AC_0) is the ID. So we just assume that.
    device = AirtouchDevice(
        host,
        entry.data.get("console_id", ""),
        entry.data.get("model", "AirTouch5"),
        entry.data.get("system_id", 0),
        entry.data.get("name", "Unknown Device"),
    )
    client = Airtouch5SimpleClient(host)
    client.device = device

    # Connect to the API
    try:
        await client.connect_and_stay_connected()
    except TimeoutError as t:
        raise ConfigEntryNotReady from t

    # Store an API object for your platforms to access
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Airtouch5ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = entry.runtime_data
        await client.disconnect()
        client.ac_status_callbacks.clear()
        client.connection_state_callbacks.clear()
        client.data_packet_callbacks.clear()
        client.zone_status_callbacks.clear()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: Airtouch5ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "async_migrate_entry called: version=%s, minor_version=%s, unique_id=%s, data=%s",
        entry.version,
        entry.minor_version,
        entry.unique_id,
        entry.data,
    )
    if entry.minor_version == 1:
        host = entry.data[CONF_HOST]
        _LOGGER.info("Migration v1→v2 starting for host=%s", host)
        try:
            identifier = entry.unique_id
            _LOGGER.info("Entry unique_id=%s", identifier)
            assert identifier is not None
            AirtouchDiscovery_instance = AirtouchDiscovery()
            _LOGGER.info("Starting AirtouchDiscovery establish_server")
            await AirtouchDiscovery_instance.establish_server()
            _LOGGER.debug(
                "AirtouchDiscovery server established, calling discover_by_ip(%s)", host
            )
            airtouch_device = await AirtouchDiscovery_instance.discover_by_ip(host)
            _LOGGER.debug(
                "Finished waiting for airtouch device: result=%s",
                airtouch_device,
            )
            if airtouch_device is not None:
                _LOGGER.debug(
                    "Discovered device: system_id=%s, ip=%s, model=%s, console_id=%s, name=%s",
                    airtouch_device.system_id,
                    airtouch_device.ip,
                    airtouch_device.model,
                    airtouch_device.console_id,
                    airtouch_device.name,
                )
            assert airtouch_device is not None, "Device not found during migration"
            # If for some reason the device is not found during migration, it will fail and will retry next time. This could leave a persistent error if the device cannout route UDP.
            new_data = {
                "system_id": airtouch_device.system_id,
                "host": airtouch_device.ip,
                "model": airtouch_device.model,
                "console_id": airtouch_device.console_id,
                "name": airtouch_device.name,
            }
            _LOGGER.info("New config entry data will be: %s", new_data)
        except TimeoutError as exception:
            _LOGGER.error("Error while migrating: %s", exception)
            return False
        finally:
            await AirtouchDiscovery_instance.close()
        # looking for climate entities
        entity_registry = er.async_get(hass)

        domain_entities = [
            e for e in entity_registry.entities.values() if e.platform == DOMAIN
        ]
        _LOGGER.debug(
            "Found %d entities for platform %s in registry",
            len(domain_entities),
            DOMAIN,
        )

        # Maps HA device_id → new DOMAIN identifier, built while iterating entities.
        # Multiple entities can share a device (e.g. climate + cover for same zone),
        # so we collect first and apply once.
        device_id_to_new_identifier: dict[str, str] = {}

        for entity in list(entity_registry.entities.values()):
            if entity.platform != DOMAIN:
                continue

            _LOGGER.debug(
                "Processing entity: entity_id=%s, unique_id=%s, domain=%s, platform=%s",
                entity.entity_id,
                entity.unique_id,
                entity.domain,
                entity.platform,
            )

            new_unique_id = build_new_unique_id(
                entity.unique_id,
                airtouch_device.system_id,
            )
            _LOGGER.debug(
                "build_new_unique_id(%s, %s) → %s",
                entity.unique_id,
                airtouch_device.system_id,
                new_unique_id,
            )

            # nothing to do
            if not new_unique_id:
                _LOGGER.debug(
                    "Skipping %s: build_new_unique_id returned None", entity.unique_id
                )
                continue

            # already correct → skip
            if entity.unique_id == new_unique_id:
                _LOGGER.debug(
                    "Skipping %s: unique_id already matches new id", entity.unique_id
                )
                continue

            # optional safety check: prevent accidental overwrite
            existing = entity_registry.async_get_entity_id(
                entity.domain,
                DOMAIN,
                new_unique_id,
            )
            _LOGGER.debug(
                "Collision check for new_unique_id=%s: existing entity_id=%s",
                new_unique_id,
                existing,
            )

            if existing and existing != entity.entity_id:
                _LOGGER.warning(
                    "Skipping %s → %s (already used)",
                    entity.unique_id,
                    new_unique_id,
                )
                continue

            _LOGGER.debug(
                "Updating entity %s: unique_id %s → %s",
                entity.entity_id,
                entity.unique_id,
                new_unique_id,
            )
            entity_registry.async_update_entity(
                entity.entity_id,
                new_unique_id=new_unique_id,
            )
            _LOGGER.debug(
                "Found entity: %s (unique_id=%s) new ID=%s",
                entity.entity_id,
                entity.unique_id,
                new_unique_id,
            )

            # Track the device identifier that should correspond to this entity.
            # For covers the device identifier is the zone id without the suffix.
            new_device_identifier = build_new_device_identifier(
                entity.unique_id, airtouch_device.system_id
            )
            if entity.device_id and new_device_identifier:
                device_id_to_new_identifier[entity.device_id] = new_device_identifier
                _LOGGER.debug(
                    "Queued device update: device_id=%s → identifier=%s",
                    entity.device_id,
                    new_device_identifier,
                )

        # Migrate device registry identifiers
        device_registry = dr.async_get(hass)
        for device_id, new_identifier in device_id_to_new_identifier.items():
            device = device_registry.async_get(device_id)
            if not device:
                _LOGGER.warning("Device %s not found in registry, skipping", device_id)
                continue
            old_domain_ids = {i for i in device.identifiers if i[0] == DOMAIN}
            new_identifiers = (device.identifiers - old_domain_ids) | {
                (DOMAIN, new_identifier)
            }
            _LOGGER.debug(
                "Updating device %s: identifiers %s → %s",
                device_id,
                old_domain_ids,
                new_identifiers,
            )
            device_registry.async_update_device(
                device_id, new_identifiers=new_identifiers
            )
        _LOGGER.debug("Updating config entry to minor_version=2 with data=%s", new_data)
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            minor_version=2,
        )
        _LOGGER.debug("Migration v1→v2 complete")
    else:
        _LOGGER.debug("No migration needed: minor_version=%s", entry.minor_version)

    return True


def build_new_unique_id(old_uid: str, system_id: str) -> str | None:
    """Map legacy Airtouch IDs to new stable format."""
    _LOGGER.debug("build_new_unique_id: old_uid=%r, system_id=%r", old_uid, system_id)

    # already migrated → skip
    if old_uid.startswith(f"{system_id}"):
        _LOGGER.debug(
            "build_new_unique_id: already starts with system_id → returning None"
        )
        return None

    # legacy AC
    if old_uid.startswith("ac_"):
        result = f"{system_id}"
        _LOGGER.debug("build_new_unique_id: matched legacy AC → %r", result)
        return result

    # legacy zones
    if old_uid.startswith("zone_"):
        parts = old_uid.split("_")
        _LOGGER.debug("build_new_unique_id: matched legacy zone, parts=%s", parts)
        if len(parts) < 2:
            _LOGGER.debug("build_new_unique_id: not enough parts → returning None")
            return None
        zone = parts[1]
        # Preserve any suffix after the zone number (e.g. "open_percentage")
        suffix = "_" + "_".join(parts[2:]) if len(parts) > 2 else ""
        result = f"{system_id}_{zone}{suffix}"
        _LOGGER.debug("build_new_unique_id: legacy zone → %r", result)
        return result

    _LOGGER.debug(
        "build_new_unique_id: no pattern matched old_uid=%r → returning None", old_uid
    )
    return None


def build_new_device_identifier(old_uid: str, system_id: str) -> str | None:
    """Return the new DOMAIN device identifier for the device that owns old_uid.

    This mirrors the device_info identifiers set in climate.py / cover.py:
    - AC entities  → (DOMAIN, system_id)
    - Zone entities (climate or cover) → (DOMAIN, f"{system_id}_{zone_number}")
    """
    if old_uid.startswith("ac_"):
        return system_id

    if old_uid.startswith("zone_"):
        parts = old_uid.split("_")
        if len(parts) >= 2:
            return f"{system_id}_{parts[1]}"

    return None
