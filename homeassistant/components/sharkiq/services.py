# Shark IQ services.

import asyncio
import json
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er, service

from .const import ATTR_ROOMS, DOMAIN
from .coordinator import SkegoxUpdateCoordinator

SERVICE_CLEAN_ROOM = "clean_room"
SERVICE_DISCOVER_DEVICE_DATA = "discover_device_data"

_LOGGER = logging.getLogger(__name__)

# Write content to a file asynchronously.
async def _async_write_file(path: Path, content: bytes | str) -> None:
    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(path, mode) as f:
            f.write(content)
    await asyncio.to_thread(_write)

# Set up services.
@callback
def async_setup_services(hass: HomeAssistant) -> None:
    # Vacuum Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_ROOM,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Required(ATTR_ROOMS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        },
        func="async_clean_room",
    )

    # Discover all available property files and data for a Skegox device.
    # Debugging dump of API data and bin files
    async def async_discover_device_data(call: ServiceCall) -> None:
        entity_id = call.data.get("entity_id")
        if not entity_id:
            _LOGGER.error("entity_id is required for discover_device_data service")
            return

        # Use entity registry to resolve entity_id to unique_id (serial number)
        entity_reg = er.async_get(hass)
        registry_entry = entity_reg.async_get(entity_id)

        if registry_entry is None:
            _LOGGER.error("Entity %s not found in registry", entity_id)
            return

        target_unique_id = registry_entry.unique_id

        # Find the Skegox coordinator that manages this device.
        coordinator = None
        target_device_serial = None

        # Iterates all config entries because there is no direct entity_id
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
                coord = entry.runtime_data
                if isinstance(coord, SkegoxUpdateCoordinator):
                    if target_unique_id in coord.shark_vacs:
                        coordinator = coord
                        # coordinator mapping in HA; the serial number (unique_id) is the link.
                        target_device_serial = target_unique_id
                        break

        if coordinator is None or target_device_serial is None:
            _LOGGER.error(
                "No Skegox device found for entity %s. "
                "This service only works with Skegox backend devices.",
                entity_id,
            )
            return
        
        device = coordinator.shark_vacs[target_device_serial]
        snd = device.serial_number
        
        if not snd:
            _LOGGER.error("Device %s has no serial number", device.name)
            return

        output_dir = Path(hass.config.path("sharkiq_discovery"))
        device_dir = output_dir / snd

        _LOGGER.info("Discovering property files for %s (%s)", device.name, snd)
        _LOGGER.info("Output directory: %s", device_dir)

        # List all available property files
        files_list = await coordinator.skegox_api.list_property_files(snd)

        # Save the file list
        file_list_path = device_dir / "property_files_list.json"
        safe_list = []
        for file_info in files_list:
            safe_info = {k: v for k, v in file_info.items() if k != "presignedUrl"}
            safe_list.append(safe_info)
        await _async_write_file(file_list_path, json.dumps(safe_list, indent=2),)

        _LOGGER.info("Found %d property files for %s", len(files_list), device.name)

        # Fetch each property file
        for file_info in files_list:
            prop_name = file_info.get("name", "unknown")
            _LOGGER.info("Fetching property file: %s", prop_name)

            content = await coordinator.skegox_api.fetch_property_file(snd, prop_name)
            if content is not None:
                # Preserve original extension for known text/binary files;
                # append .bin for everything else so the file is not misidentified.
                ext = "" if any(prop_name.endswith(e) for e in (".bin", ".txt")) else ".bin"
                file_path = device_dir / f"{prop_name}{ext}"
                await _async_write_file(file_path, content)

                # Try to parse as JSON for readability
                try:
                    parsed = json.loads(content.decode("utf-8"))
                    json_path = device_dir / f"{prop_name}.json"
                    await _async_write_file(
                        json_path,
                        json.dumps(parsed, indent=2),
                    )
                    _LOGGER.info("Saved %s as JSON (%d bytes)", prop_name, len(content))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    _LOGGER.info("Saved %s as binary (%d bytes)", prop_name, len(content))
            else:
                _LOGGER.warning("No content for property file: %s", prop_name)

        # Save device shadow data
        shadow_path = device_dir / "device_shadow.json"
        await _async_write_file(
            shadow_path,
            json.dumps(device._raw, indent=2, default=str),
        )

        # Save MARD data if available
        if device.mard_data:
            mard_path = device_dir / "MARD_full.json"
            await _async_write_file(
                mard_path,
                json.dumps(device.mard_data, indent=2),
            )

        _LOGGER.info("Discovery complete for %s. Files saved to: %s", device.name, device_dir,)

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISCOVER_DEVICE_DATA,
        async_discover_device_data,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
        }),
    )
