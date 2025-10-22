"""Camera platform for OpenH264 Nedis Camera integration."""
from __future__ import annotations
from typing import Optional
from homeassistant.components.camera import Camera, CameraEntityFeature, async_get_image, async_get_stream_source
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_ENTITY_ID
from .const import (
    DOMAIN, 
    LOGGER, 
    CONF_NAME, 
    CONF_MODE, 
    MODE_CAMERA, 
    MODE_URL,
    CONF_STREAM_URL, 
    CONF_SNAPSHOT_URL, 
    DEFAULT_NAME, 
    DEFAULT_TIMEOUT
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up OpenH264 Nedis Camera from config entry."""
    data = {**entry.data, **entry.options}
    
    camera = OpenH264NedisCamera(
        hass=hass,
        name=data.get(CONF_NAME, DEFAULT_NAME),
        mode=data.get(CONF_MODE, MODE_CAMERA),
        entity_id=data.get(CONF_ENTITY_ID),
        stream_url=data.get(CONF_STREAM_URL),
        snapshot_url=data.get(CONF_SNAPSHOT_URL),
        entry_id=entry.entry_id,
    )
    
    async_add_entities([camera])


class OpenH264NedisCamera(Camera):
    """OpenH264 Nedis Camera entity."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self, 
        hass: HomeAssistant, 
        name: str, 
        mode: str, 
        entity_id: Optional[str], 
        stream_url: Optional[str], 
        snapshot_url: Optional[str], 
        entry_id: str
    ):
        """Initialize the camera."""
        super().__init__()
        self.hass = hass
        self._attr_name = name
        self._mode = mode
        self._entity_id = entity_id
        self._stream_url = stream_url
        self._snapshot_url = snapshot_url
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"

    async def async_camera_image(self, width: Optional[int] = None, height: Optional[int] = None) -> bytes | None:
        """Return bytes of camera image."""
        try:
            # Mode 1: Proxy another camera entity
            if self._mode == MODE_CAMERA and self._entity_id:
                img = await async_get_image(
                    self.hass, 
                    self._entity_id, 
                    width=width, 
                    height=height, 
                    timeout=DEFAULT_TIMEOUT
                )
                return img.content if img else None
            
            # Mode 2: Use direct snapshot URL
            if self._mode == MODE_URL and self._snapshot_url:
                session = self.hass.helpers.aiohttp_client.async_get_clientsession()
                async with session.get(self._snapshot_url, timeout=DEFAULT_TIMEOUT) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    LOGGER.warning("HTTP %d when fetching snapshot from %s", resp.status, self._snapshot_url)
                        
        except Exception as err:
            LOGGER.warning("Failed to fetch camera image: %s", err)
        
        return None

    async def stream_source(self) -> Optional[str]:
        """Return the source of the stream."""
        try:
            # Mode 1: Get stream source from proxied camera entity
            if self._mode == MODE_CAMERA and self._entity_id:
                return await async_get_stream_source(self.hass, self._entity_id)
            
            # Mode 2: Use direct stream URL
            if self._mode == MODE_URL:
                return self._stream_url
                
        except Exception as err:
            LOGGER.warning("Failed to get stream source: %s", err)
        
        return None

    @property
    def device_info(self):
        """Return device information for the camera."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "manufacturer": "Nedis",
            "name": self._attr_name,
            "model": "OpenH264 Enhanced Camera",
            "sw_version": "0.1.0"
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self._mode == MODE_CAMERA:
            # Check if the proxied camera entity exists
            return self.hass.states.get(self._entity_id) is not None if self._entity_id else False
        elif self._mode == MODE_URL:
            # For URL mode, we assume it's available if we have at least one URL
            return bool(self._stream_url or self._snapshot_url)
        return False
