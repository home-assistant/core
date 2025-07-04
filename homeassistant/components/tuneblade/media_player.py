import logging
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerState,
    MediaPlayerEntityFeature,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    added_ids = set()
    entities = []

    # Add the MASTER hub media player first if present
    if "MASTER" in coordinator.data:
        entities.append(TuneBladeHubMediaPlayer(coordinator))
        added_ids.add("MASTER")

    async def _update_entities():
        new_entities = []

        # Add per-device media players, skip 'MASTER' (already added)
        for device_id, device_data in coordinator.data.items():
            if device_id == "MASTER":
                continue
            if device_id not in added_ids:
                entity = TuneBladeMediaPlayer(coordinator, device_id, device_data)
                new_entities.append(entity)
                added_ids.add(device_id)
                _LOGGER.debug("Added new media player: %s", device_data.get("name", device_id))

        if new_entities:
            async_add_entities(new_entities, True)

    # Add initial entities
    async_add_entities(entities)
    await _update_entities()

    # Register future additions
    coordinator.async_add_listener(_update_entities)


class TuneBladeHubMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player representing the TuneBlade MASTER hub as a service."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.device_id = "MASTER"
        self._attr_name = "Master"
        self._attr_unique_id = "tuneblade_master_media_player"
        self._attr_volume_level = None
        self._attr_state = MediaPlayerState.OFF
        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
        )

    @property
    def available(self) -> bool:
        return self.device_id in self.coordinator.data

    async def async_turn_on(self):
        _LOGGER.debug("Connecting TuneBlade Hub MASTER")
        await self.coordinator.client.connect(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        _LOGGER.debug("Disconnecting TuneBlade Hub MASTER")
        await self.coordinator.client.disconnect(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume):
        _LOGGER.debug(f"Setting volume for TuneBlade Hub MASTER: {volume}")
        await self.coordinator.client.set_volume(self.device_id, int(volume * 100))
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self._handle_coordinator_update)
        self._handle_coordinator_update()

    def _handle_coordinator_update(self):
        device_data = self.coordinator.data.get(self.device_id)
        if device_data is None:
            self._attr_state = MediaPlayerState.OFF
            self._attr_volume_level = None
        else:
            code = str(device_data.get("status_code", "0"))
            if code == "100":
                self._attr_state = MediaPlayerState.PLAYING
            elif code == "200":
                self._attr_state = MediaPlayerState.IDLE
            elif code == "0":
                self._attr_state = MediaPlayerState.OFF
            else:
                self._attr_state = MediaPlayerState.OFF

            volume = device_data.get("volume")
            self._attr_volume_level = volume / 100 if volume is not None else None

        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        device_data = self.coordinator.data.get(self.device_id, {})
        code = str(device_data.get("status_code", "0"))
        status_map = {
            "0": "disconnected",
            "100": "playing",
            "200": "standby",
        }

        return {
            "device_name": device_data.get("name", "MASTER"),
            "status_code": code,
            "status_text": status_map.get(code, "unknown"),
            "volume": device_data.get("volume"),
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "MASTER")},
            "name": self._attr_name,
            "manufacturer": "TuneBlade",
            "entry_type": "service",  # Mark as hub/service device
        }


class TuneBladeMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player for individual TuneBlade devices."""

    def __init__(self, coordinator, device_id, device_data):
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_name = device_data["name"]
        safe_name = self._attr_name.replace(" ", "_")
        self._attr_unique_id = f"{device_id}@{safe_name}"
        self._attr_volume_level = None
        self._attr_state = MediaPlayerState.OFF
        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
        )

    @property
    def available(self) -> bool:
        return self.device_id in self.coordinator.data

    async def async_turn_on(self):
        await self.coordinator.client.connect(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        await self.coordinator.client.disconnect(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume):
        await self.coordinator.client.set_volume(self.device_id, int(volume * 100))
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Register callback when entity is added."""
        self.coordinator.async_add_listener(self._handle_coordinator_update)
        self._handle_coordinator_update()

    def _handle_coordinator_update(self):
        device_data = self.coordinator.data.get(self.device_id)
        if device_data is None:
            self._attr_state = MediaPlayerState.OFF
            self._attr_volume_level = None
        else:
            code = str(device_data.get("status_code", "0"))
            if code == "100":
                self._attr_state = MediaPlayerState.PLAYING
            elif code == "200":
                self._attr_state = MediaPlayerState.IDLE
            elif code == "0":
                self._attr_state = MediaPlayerState.OFF
            else:
                self._attr_state = MediaPlayerState.OFF

            volume = device_data.get("volume")
            self._attr_volume_level = volume / 100 if volume is not None else None

        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        device_data = self.coordinator.data.get(self.device_id, {})
        code = str(device_data.get("status_code", "0"))
        status_map = {
            "0": "disconnected",
            "100": "playing",
            "200": "standby",
        }

        return {
            "device_name": device_data.get("name"),
            "status_code": code,
            "status_text": status_map.get(code, "unknown"),
            "volume": device_data.get("volume"),
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "via_device": (DOMAIN, "MASTER"),  # Link media player to hub device
            "name": self._attr_name,
            "manufacturer": "TuneBlade",
        }
