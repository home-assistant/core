"""TuneBlade Remote media player entity."""

import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TuneBladeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TuneBlade Remote from a config entry."""
    coordinator: TuneBladeDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    added_ids = set()
    entities: list[MediaPlayerEntity] = []

    for device_id, device_data in coordinator.data.items():
        if device_id == "MASTER":
            entities.append(TuneBladeHubMediaPlayer(coordinator))
            added_ids.add("MASTER")
        elif device_id not in added_ids:
            # Create a media player entity for each device
            entities.append(TuneBladeMediaPlayer(coordinator, device_id, device_data))
            added_ids.add(device_id)
            _LOGGER.debug(
                "Added new media player: %s", device_data.get("name", device_id)
            )

    if entities:
        async_add_entities(entities, True)


class TuneBladeHubMediaPlayer(
    CoordinatorEntity[TuneBladeDataUpdateCoordinator], MediaPlayerEntity
):
    """Media player representing the TuneBlade MASTER hub as a service."""

    def __init__(self, coordinator: TuneBladeDataUpdateCoordinator) -> None:
        """Initialize the entity."""
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
        """Return True if the device is available."""
        return self.device_id in self.coordinator.data

    async def async_turn_on(self) -> None:
        """Turn on the media player."""
        _LOGGER.debug("Connecting TuneBlade Hub MASTER")
        await self.coordinator.client.connect(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the media player."""
        _LOGGER.debug("Disconnecting TuneBlade Hub MASTER")
        await self.coordinator.client.disconnect(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level for TuneBlade MASTER."""
        _LOGGER.debug("Setting volume for TuneBlade Hub MASTER: %s", volume)
        await self.coordinator.client.set_volume(self.device_id, int(volume * 100))
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Register the coordinator update listener."""
        await super().async_added_to_hass()
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
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return extra attributes for the TuneBlade MASTER media player."""
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
    def device_info(self) -> DeviceInfo | None:
        """Return device info for the TuneBlade MASTER media player."""
        return DeviceInfo(
            identifiers={(DOMAIN, "MASTER")},
            name=self._attr_name,
            manufacturer="TuneBlade",
            entry_type=DeviceEntryType.SERVICE,
        )


class TuneBladeMediaPlayer(
    CoordinatorEntity[TuneBladeDataUpdateCoordinator], MediaPlayerEntity
):
    """Media player for individual TuneBlade devices."""

    def __init__(
        self,
        coordinator: TuneBladeDataUpdateCoordinator,
        device_id: str,
        device_data: dict,
    ) -> None:
        """Initialize the media player entity."""
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
        """Return True if the device is available."""
        return self.device_id in self.coordinator.data

    async def async_turn_on(self) -> None:
        """Turn on the media player."""
        await self.coordinator.client.connect(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the media player."""
        await self.coordinator.client.disconnect(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level for the media player."""
        await self.coordinator.client.set_volume(self.device_id, int(volume * 100))
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Register the coordinator update listener."""
        await super().async_added_to_hass()
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
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return extra attributes for the media player."""
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
    def device_info(self) -> DeviceInfo | None:
        """Return device info for the media player."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            via_device=(DOMAIN, "MASTER"),
            name=self._attr_name,
            manufacturer="TuneBlade",
        )
