from __future__ import annotations

import json
import logging
import math
from typing import Optional, List, Dict, Any
import aiohttp
import time
from google.auth import jwt
from google.auth.crypt import rsa

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_track_state_change_event

from oasira import OasiraAPIClient, OasiraAPIError
from .const import DOMAIN, NAME, ATTR_LATITUDE, ATTR_LONGITUDE
from .notificationdevice import effortlesshomenotificationdevice
from .auth_helper import safe_api_call

_LOGGER = logging.getLogger(__name__)


GOOGLE_OAUTH_URL = "https://oauth2.googleapis.com/token"
FIREBASE_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"

FCM_URL = "https://fcm.googleapis.com/v1/projects/oasira-oauth/messages:send"


class eh_person(SensorEntity, RestoreEntity):
    """A persistent, sensor-like representation of an EffortlessHome Person with tracking and notifications."""

    def __init__(self, hass: Optional[HomeAssistant], email: str):
        self.hass = hass
        self._email = email
        self._attr_name = email
        self._attr_unique_id = f"effortlesshome_person_{email.lower().replace('@', '_').replace('.', '_')}"
        self._attr_icon = "mdi:account"
        self._attr_should_poll = False

        self._local_tracker_entity_id: Optional[str] = None
        self._remote_tracker_entity_id: Optional[str] = None
        self._notification_devices: List[effortlesshomenotificationdevice] = []
        self._health_data: Dict[str, Any] = {}

        # Device registry
        self._device_registry = async_get_dev_reg(hass) if hass else None
        self._device_id = None

        

    # ---- Standard HA Properties ----
    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def icon(self) -> str:
        return "mdi:account-group"

    @property
    def state(self) -> str:
        return self.remotetracker + "|"+ self.localtracker

    @property
    def name(self) -> str:
        return self._email

    @property
    def notification_devices(self) -> List[effortlesshomenotificationdevice]:
        return self._notification_devices

    @property
    def device_info(self) -> Dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def localtracker(self) -> str:
        # Local tracker
        if self._local_tracker_entity_id:
            entity = self.hass.states.get(self._local_tracker_entity_id)
            if entity is not None:
                return entity.state
            else:
                return "unknown"
        else:
            return "unknown"


    @property
    def remotetracker(self) -> str:
        # Remote tracker
        if self._remote_tracker_entity_id:
            entity = self.hass.states.get(self._remote_tracker_entity_id)
            if entity is not None:
                return entity.state
            else:
                return "unknown"
        else:
            return "unknown"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return attributes for Home Assistant."""

        return {
            "effortlesshome_type": "eh_person",
            "email": self._email,
            "local_tracker": self._local_tracker_entity_id,
            "remote_tracker": self._remote_tracker_entity_id,
            "notification_devices": [d.to_json() for d in self._notification_devices],
            "health_data_last_updated": self._health_data.get("timestamp"),
        }

    # ---- Serialization ----
    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "email": self._email,
            "unique_id": self._attr_unique_id,
            "local_tracker": self._local_tracker_entity_id,
            "remote_tracker": self._remote_tracker_entity_id,
            "notification_devices": [d.to_dict() for d in self._notification_devices],
        }

    def to_json(self) -> str:
        """Return JSON string representation."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "eh_person":
        """Reconstruct from serialized dictionary (hass can be attached later)."""
        obj = cls(
            hass=None,
            email=data.get("email", ""),
        )
        obj._local_tracker_entity_id = data.get("local_tracker")
        obj._remote_tracker_entity_id = data.get("remote_tracker")
        obj._notification_devices = [
            effortlesshomenotificationdevice.from_dict(d)
            for d in data.get("notification_devices", [])
        ]
        return obj

    # ---- Device linking ----
    async def async_set_local_tracker(self, entity_id: str):
        self._local_tracker_entity_id = entity_id
        _LOGGER.info("[eh_person] Linked local tracker for %s: %s", self._email, entity_id)
        self.async_write_ha_state()
        
        # Set up geofencing for the new tracker
        await self.async_setup_geofencing()

    async def async_set_remote_tracker(self, entity_id: str):
        self._remote_tracker_entity_id = entity_id
        _LOGGER.info("[eh_person] Linked remote tracker for %s: %s", self._email, entity_id)
        self.async_write_ha_state()
        
        # Set up geofencing for the new tracker
        await self.async_setup_geofencing()

    async def async_set_notification_devices(
        self, hass: HomeAssistant, token: str, device_name: str, platform_name: str
    ):
        """Link a notification device."""
        if not token:
            _LOGGER.warning("[eh_person] Missing token for notification registration.")
            return

        existing = next((d for d in self._notification_devices if d.Name == device_name), None)
        if existing:
            _LOGGER.info("[eh_person] Device %s already registered for %s", device_name, self._email)

            #update mode
            existing.DeviceToken = token
            existing.Platform = platform_name
            self.async_write_ha_state()
            _LOGGER.info("[eh_person] Updated notification device %s for %s", device_name, self._email)

        else:
            device = effortlesshomenotificationdevice(hass, token, device_name, platform_name)
            self._notification_devices.append(device)
            self.async_write_ha_state()
            _LOGGER.info("[eh_person] Added notification device %s for %s", device_name, self._email)

    async def async_remove_notification_devices(
        self, hass: HomeAssistant
    ):
        """Remove all notification devices."""
        if not self._notification_devices:
            _LOGGER.info("[eh_person] No notification devices to remove for %s", self._email)
            return      
        else:
            self._notification_devices.clear()
            self.async_write_ha_state()
            _LOGGER.info("[eh_person] Removed all notification devices for %s", self._email)


    async def async_added_to_hass(self):
        """Handle entity addition and restore previous state."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is None:
            _LOGGER.info("[eh_person] No previous state to restore for %s", self._email)
            return

        attrs = last_state.attributes or {}
        self._local_tracker_entity_id = attrs.get("local_tracker")
        self._remote_tracker_entity_id = attrs.get("remote_tracker")

        restored_devices_raw = attrs.get("notification_devices")
        _LOGGER.debug("[eh_person] Raw restored notification_devices: (%s) %r",
                    type(restored_devices_raw).__name__, restored_devices_raw)

        devices_list: list = []

        def try_parse_json_string(s: str) -> list:
            """Try several ways to parse a JSON string into a list of dicts."""
            s_stripped = s.strip()
            _LOGGER.debug("[eh_person] Attempting to parse JSON string chunk: %r", s_stripped[:200])
            # 1) Try direct load (handles object or array)
            try:
                parsed = json.loads(s_stripped)
                if isinstance(parsed, list):
                    _LOGGER.debug("[eh_person] Parsed JSON as list with %d items", len(parsed))
                    return parsed
                if isinstance(parsed, dict):
                    _LOGGER.debug("[eh_person] Parsed JSON as single object")
                    return [parsed]
            except json.JSONDecodeError as e:
                _LOGGER.debug("[eh_person] Direct json.loads failed: %s", e)

            # 2) If looks like multiple objects without surrounding brackets, try wrapping
            if s_stripped.startswith("{") and s_stripped.endswith("}"):
                wrapped = f"[{s_stripped}]"
                try:
                    parsed = json.loads(wrapped)
                    _LOGGER.debug("[eh_person] Parsed by wrapping in brackets -> %d items", len(parsed))
                    return parsed
                except json.JSONDecodeError as e:
                    _LOGGER.debug("[eh_person] Wrapped json.loads failed: %s", e)

            # 3) As a last resort attempt to convert a "}, {" pattern into a valid array
            if "},{" in s_stripped or "}, {" in s_stripped:
                # Insert array brackets if missing
                candidate = s_stripped
                if not candidate.startswith("["):
                    candidate = "[" + candidate
                if not candidate.endswith("]"):
                    candidate = candidate + "]"
                try:
                    parsed = json.loads(candidate)
                    _LOGGER.debug("[eh_person] Parsed by forcing array brackets -> %d items", len(parsed))
                    return parsed
                except json.JSONDecodeError as e:
                    _LOGGER.debug("[eh_person] Forced-array json.loads failed: %s", e)

            _LOGGER.warning("[eh_person] Failed to parse JSON chunk; skipping. chunk preview: %r", s_stripped[:200])
            return []

        # If it's a list, individual elements may be dicts or JSON strings
        if isinstance(restored_devices_raw, list):
            _LOGGER.debug("[eh_person] notification_devices is a list with %d elements", len(restored_devices_raw))
            for idx, item in enumerate(restored_devices_raw):
                _LOGGER.debug("[eh_person] Inspecting list element %d type=%s", idx, type(item).__name__)
                if isinstance(item, dict):
                    devices_list.append(item)
                elif isinstance(item, str):
                    parsed = try_parse_json_string(item)
                    devices_list.extend([p for p in parsed if isinstance(p, dict)])
                else:
                    _LOGGER.warning("[eh_person] Unsupported list element type in notification_devices: %s", type(item))
        elif isinstance(restored_devices_raw, str):
            # The attribute is a string; it may contain one or many JSON objects (or an array string)
            parsed = try_parse_json_string(restored_devices_raw)
            devices_list.extend([p for p in parsed if isinstance(p, dict)])
        elif restored_devices_raw is None:
            _LOGGER.info("[eh_person] No notification_devices attribute to restore for %s", self._email)
        else:
            _LOGGER.warning("[eh_person] Unexpected type for notification_devices: %s", type(restored_devices_raw))

        _LOGGER.debug("[eh_person] Devices parsed count=%d : %s",
                    len(devices_list), [d.get("name") for d in devices_list])

        # Reconstruct device objects safely
        restored_objs = []
        for d_idx, d in enumerate(devices_list):
            if not isinstance(d, dict):
                _LOGGER.debug("[eh_person] Skipping non-dict device entry at index %d: %r", d_idx, d)
                continue
            try:
                # prefer a from_dict constructor if available
                if hasattr(effortlesshomenotificationdevice, "from_dict"):
                    obj = effortlesshomenotificationdevice.from_dict(d)
                    # attach hass if possible so the object behaves inside HA
                    try:
                        obj.hass = self.hass
                    except Exception:
                        pass
                else:
                    # fallback to direct init using expected fields
                    obj = effortlesshomenotificationdevice(
                        self.hass,
                        token=d.get("token", ""),
                        name=d.get("name", d.get("unique_id", "unknown")),
                        platform=d.get("platform", ""),
                    )
                    obj._state = d.get("state", "available")
                restored_objs.append(obj)
                _LOGGER.info("[eh_person] Restored notification device: %s", getattr(obj, "Name", d.get("name")))
            except Exception as e:
                _LOGGER.exception("[eh_person] Failed to reconstruct device from dict %r: %s", d, e)

        self._notification_devices = restored_objs

        _LOGGER.info(
            "[eh_person] Restored %d notification devices for %s",
            len(self._notification_devices),
            self._email,
        )

        # Set up geofencing after restoration
        await self.async_setup_geofencing()

    async def async_get_firebase_access_token(self) -> str:
        """Generate a Firebase access token using service account JSON (async + HA safe)."""

        try:
            # ---- Fetch service account JSON using API client ----
            # Get the id_token from hass.data for authentication
            id_token = self.hass.data[DOMAIN].get("id_token") if self.hass else None
            
            async with OasiraAPIClient(id_token=id_token) as client:
                firebase_config = await client.get_firebase_config()

            google_firebase_raw = firebase_config.get("Google_Firebase")
            if not google_firebase_raw:
                _LOGGER.error("Missing Google_Firebase in response")
                return None

            service_account_info = json.loads(google_firebase_raw)

            private_key = service_account_info["private_key"]
            client_email = service_account_info["client_email"]

            # ---- Build JWT ----
            now = int(time.time())
            payload = {
                "iss": client_email,
                "scope": FIREBASE_SCOPE,
                "aud": GOOGLE_OAUTH_URL,
                "iat": now,
                "exp": now + 3600,
            }

            signer = rsa.RSASigner.from_string(private_key)
            assertion = jwt.encode(signer, payload)

            # ---- Exchange JWT for OAuth access token ----
            form = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(GOOGLE_OAUTH_URL, data=form) as resp:
                    result = await resp.json()

                    if "access_token" not in result:
                        _LOGGER.error("Firebase OAuth error: %s", result)
                        return None

                    return result["access_token"]

        except OasiraAPIError as e:
            _LOGGER.error("Failed to fetch Firebase config: %s", e)
            return None
        except Exception as e:
            _LOGGER.exception("Failed to refresh Firebase access token: %s", e)
            return None


    def __repr__(self):
        return f"<eh_person email={self._email!r} devices={len(self._notification_devices)}>"


    # ---- Geofencing functionality ----
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using haversine formula."""
        # Earth's radius in meters
        R = 6371000
        
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance

    def _get_home_coordinates(self) -> Optional[tuple]:
        """Get home coordinates from system configuration."""
        try:
            # Try to get home coordinates from system configuration
            system_data = self.hass.data.get(DOMAIN, {})
            address_json = system_data.get("address_json")
            
            if address_json:
                # Parse address JSON to extract coordinates
                # This assumes the address_json contains latitude and longitude
                if isinstance(address_json, str):
                    address_data = json.loads(address_json)
                else:
                    address_data = address_json
                
                lat = address_data.get("latitude")
                lon = address_data.get("longitude")
                
                if lat is not None and lon is not None:
                    return (float(lat), float(lon))
                    
        except Exception as e:
            _LOGGER.debug("[eh_person] Could not get home coordinates from system config: %s", e)
        
        # Fallback: try to get coordinates from Home Assistant configuration
        try:
            home_lat = self.hass.config.latitude
            home_lon = self.hass.config.longitude
            
            if home_lat is not None and home_lon is not None:
                return (float(home_lat), float(home_lon))
                
        except Exception as e:
            _LOGGER.debug("[eh_person] Could not get home coordinates from HA config: %s", e)
        
        return None

    def _get_geofence_radius(self) -> float:
        """Get geofence radius in meters from configuration."""
        # Default radius: 100 meters
        return 100.0

    def _calculate_dynamic_state(self, tracker_state: str, entity_id: str) -> str:
        """Calculate dynamic home/away state based on location."""
        if tracker_state in ["home", "not_home"]:
            # If the tracker already has a clear state, use it
            return tracker_state
        
        # Get current location from the tracker entity
        entity = self.hass.states.get(entity_id)
        if not entity:
            return "unknown"
        
        # Get latitude and longitude from entity attributes
        lat = entity.attributes.get(ATTR_LATITUDE)
        lon = entity.attributes.get(ATTR_LONGITUDE)
        
        if lat is None or lon is None:
            return "unknown"
        
        # Get home coordinates
        home_coords = self._get_home_coordinates()
        if not home_coords:
            _LOGGER.warning("[eh_person] No home coordinates available for geofencing")
            return "unknown"
        
        home_lat, home_lon = home_coords
        
        # Calculate distance
        distance = self._calculate_distance(lat, lon, home_lat, home_lon)
        radius = self._get_geofence_radius()
        
        # Determine state based on distance
        if distance <= radius:
            return "home"
        else:
            return "not_home"

    async def _update_tracker_state(self, entity_id: str, new_state: str):
        """Update tracker state and trigger state change if needed."""
        if entity_id == self._local_tracker_entity_id:
            # Update local tracker
            if hasattr(self, '_local_tracker_state'):
                old_state = self._local_tracker_state
            else:
                old_state = "unknown"
            
            self._local_tracker_state = new_state
            
            if old_state != new_state:
                _LOGGER.info("[eh_person] Local tracker state changed for %s: %s -> %s", 
                           self._email, old_state, new_state)
                self.async_write_ha_state()
        
        elif entity_id == self._remote_tracker_entity_id:
            # Update remote tracker
            if hasattr(self, '_remote_tracker_state'):
                old_state = self._remote_tracker_state
            else:
                old_state = "unknown"
            
            self._remote_tracker_state = new_state
            
            if old_state != new_state:
                _LOGGER.info("[eh_person] Remote tracker state changed for %s: %s -> %s", 
                           self._email, old_state, new_state)
                self.async_write_ha_state()

    async def _handle_location_change(self, entity_id: str, old_state, new_state):
        """Handle location changes from device trackers."""
        if entity_id not in [self._local_tracker_entity_id, self._remote_tracker_entity_id]:
            return
        
        # Calculate dynamic state based on new location
        dynamic_state = self._calculate_dynamic_state(new_state.state if new_state else "unknown", entity_id)
        
        if dynamic_state != "unknown":
            await self._update_tracker_state(entity_id, dynamic_state)

    async def async_setup_geofencing(self):
        """Set up geofencing for linked trackers."""
        if not self._local_tracker_entity_id and not self._remote_tracker_entity_id:
            return
        
        # Set up state change listeners for both trackers
        if self._local_tracker_entity_id:
            async_track_state_change_event(
                self.hass,
                self._local_tracker_entity_id,
                self._handle_location_change
            )
            _LOGGER.info("[eh_person] Set up geofencing for local tracker: %s", self._local_tracker_entity_id)
        
        if self._remote_tracker_entity_id:
            async_track_state_change_event(
                self.hass,
                self._remote_tracker_entity_id,
                self._handle_location_change
            )
            _LOGGER.info("[eh_person] Set up geofencing for remote tracker: %s", self._remote_tracker_entity_id)
