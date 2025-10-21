"""The OpenH264 Nedis Camera integration."""
from __future__ import annotations
import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, ServiceCall
from homeassistant.const import Platform
from homeassistant.helpers import service
from .const import DOMAIN, LOGGER, CONF_LIB_PATH
from .encoder import OpenH264Encoder

PLATFORMS: list[Platform] = [Platform.CAMERA]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenH264 Nedis Camera from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    data = dict(entry.data)
    options = dict(entry.options)
    
    # Initialize the OpenH264 encoder
    lib_path = options.get(CONF_LIB_PATH) or data.get(CONF_LIB_PATH)
    encoder = OpenH264Encoder(lib_path)
    
    # Store integration data
    hass.data[DOMAIN][entry.entry_id] = {
        "config": data,
        "options": options,
        "encoder": encoder
    }

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register services
    await _async_register_services(hass)
    
    LOGGER.info("OpenH264 Nedis Camera integration loaded for entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        LOGGER.info("OpenH264 Nedis Camera integration unloaded for entry %s", entry.entry_id)
    
    return unload_ok


@callback
async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    LOGGER.debug("Reloading OpenH264 Nedis Camera integration due to options change")
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    
    @service.verify_domain_control(hass, DOMAIN)
    async def handle_encode_file(call: ServiceCall):
        """Handle encode_file service call."""
        input_path = call.data.get("input_path")
        output_path = call.data.get("output_path")
        LOGGER.info("encode_file service called: %s -> %s", input_path, output_path)
        
        # TODO: Implement actual file encoding using OpenH264
        # For now, this is a placeholder that logs the service call
        if input_path and output_path:
            if not os.path.exists(input_path):
                LOGGER.error("Input file does not exist: %s", input_path)
                return
            
            # Future implementation will use encoder.encode_file()
            LOGGER.info("File encoding requested but not yet implemented")
        else:
            LOGGER.error("Missing required parameters: input_path and output_path")

    @service.verify_domain_control(hass, DOMAIN)  
    async def handle_capture_snapshot(call: ServiceCall):
        """Handle capture_snapshot service call."""
        entity_id = call.data.get("entity_id")
        filename = call.data.get("filename")
        LOGGER.info("capture_snapshot service called: %s -> %s", entity_id, filename)
        
        # TODO: Implement snapshot capture
        # This will get the camera image and save to file
        if entity_id and filename:
            # Future implementation will:
            # 1. Get camera entity from entity_id
            # 2. Call async_camera_image()
            # 3. Save image bytes to filename
            LOGGER.info("Snapshot capture requested but not yet implemented")
        else:
            LOGGER.error("Missing required parameters: entity_id and filename")

    @service.verify_domain_control(hass, DOMAIN)
    async def handle_record_clip(call: ServiceCall):
        """Handle record_clip service call."""
        entity_id = call.data.get("entity_id")
        filename = call.data.get("filename")
        duration = call.data.get("duration", 30)
        LOGGER.info("record_clip service called: %s -> %s (%ds)", entity_id, filename, duration)
        
        # TODO: Implement clip recording
        # This will delegate to HA's camera.record service or implement custom recording
        if entity_id and filename:
            # Future implementation will use HA's camera.record service
            LOGGER.info("Clip recording requested but not yet implemented")
        else:
            LOGGER.error("Missing required parameters: entity_id and filename")

    # Register all services
    hass.services.async_register(DOMAIN, "encode_file", handle_encode_file)
    hass.services.async_register(DOMAIN, "capture_snapshot", handle_capture_snapshot)  
    hass.services.async_register(DOMAIN, "record_clip", handle_record_clip)