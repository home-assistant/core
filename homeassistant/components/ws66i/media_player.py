"""Support for interfacing with WS66i 6 zone home audio controller."""
import logging

from pyws66i import WS66i, ZoneStatus

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICE_RESTORE, SERVICE_SNAPSHOT
from .coordinator import Ws66iDataUpdateCoordinator
from .models import Ws66iData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

SUPPORT_WS66I = (
    SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WS66i 6-zone amplifier platform from a config entry."""
    ws66i_data: Ws66iData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for idx, zone_id in enumerate(ws66i_data.zones):
        entities.append(
            Ws66iZone(
                device=ws66i_data.device,
                ws66i_data=ws66i_data,
                entry_id=config_entry.entry_id,
                zone_id=zone_id,
                idx=idx,
                coordinator=ws66i_data.coordinator,
            )
        )

    # Add them to HA
    async_add_entities(entities)

    # Set up services
    platform = async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SNAPSHOT,
        {},
        "snapshot",
    )

    platform.async_register_entity_service(
        SERVICE_RESTORE,
        {},
        "restore",
    )


class Ws66iZone(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a WS66i amplifier zone."""

    def __init__(
        self,
        device: WS66i,
        ws66i_data: Ws66iData,
        entry_id: str,
        zone_id: int,
        idx: int,
        coordinator: Ws66iDataUpdateCoordinator,
    ) -> None:
        """Initialize a zone entity."""
        super().__init__(coordinator)
        self._ws66i: WS66i = device
        self._ws66i_data: Ws66iData = ws66i_data
        self._zone_id: int = zone_id
        self._zone_id_idx: int = idx
        self._coordinator = coordinator
        self._snapshot = None
        self._volume = None
        self._attr_source_list = ws66i_data.sources.name_list
        self._attr_unique_id = f"{entry_id}_{self._zone_id}"
        self._attr_name = f"Zone {self._zone_id}"
        self._attr_supported_features = SUPPORT_WS66I
        self._attr_is_volume_muted = None
        self._attr_source = None
        self._attr_state = None
        self._attr_media_title = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.unique_id))},
            name=self.name,
            manufacturer="Soundavo",
            model="WS66i 6-Zone Amplifier",
        )

        # Check if coordinator has data for this zone, and update values
        data: list[ZoneStatus] = self.coordinator.data
        if data is not None:
            self._update_zone(data[self._zone_id_idx])

    @callback
    def _update_zone(self, zone_status: ZoneStatus) -> None:
        """Update internal fields from a ZoneStatus."""
        self._attr_state = STATE_ON if zone_status.power else STATE_OFF
        self._volume = zone_status.volume
        self._attr_is_volume_muted = zone_status.mute
        idx = zone_status.source
        if idx in self._ws66i_data.sources.id_name:
            self._attr_source = self._ws66i_data.sources.id_name[idx]
            self._attr_media_title = self._ws66i_data.sources.id_name[idx]
        else:
            self._attr_source = None
            self._attr_media_title = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # This will be called for each of my entities after the coordinator
        # finishes executing _async_update_data()

        # Grab the zone status that this entity represents
        zone_status: ZoneStatus = self.coordinator.data[self._zone_id_idx]
        self._update_zone(zone_status)

        # Parent will notify HA that our fields were updated
        super()._handle_coordinator_update()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is None:
            return None
        return self._volume / 38.0

    def snapshot(self):
        """Save zone's current state."""
        self._snapshot = self._ws66i.zone_status(self._zone_id)

    def restore(self):
        """Restore saved state."""
        if self._snapshot:
            self._ws66i.restore_zone(self._snapshot)
            self.schedule_update_ha_state(True)

    def select_source(self, source):
        """Set input source."""
        if source not in self._ws66i_data.sources.name_id:
            return
        idx = self._ws66i_data.sources.name_id[source]
        self._ws66i.set_source(self._zone_id, idx)
        self.schedule_update_ha_state(True)

    def turn_on(self):
        """Turn the media player on."""
        self._ws66i.set_power(self._zone_id, True)
        self.schedule_update_ha_state(True)

    def turn_off(self):
        """Turn the media player off."""
        self._ws66i.set_power(self._zone_id, False)
        self.schedule_update_ha_state(True)

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._ws66i.set_mute(self._zone_id, mute)
        self.schedule_update_ha_state(True)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._ws66i.set_volume(self._zone_id, int(volume * 38))
        self.schedule_update_ha_state(True)

    def volume_up(self):
        """Volume up the media player."""
        if self._volume is None:
            return
        self._ws66i.set_volume(self._zone_id, min(self._volume + 1, 38))
        self.schedule_update_ha_state(True)

    def volume_down(self):
        """Volume down media player."""
        if self._volume is None:
            return
        self._ws66i.set_volume(self._zone_id, max(self._volume - 1, 0))
        self.schedule_update_ha_state(True)
