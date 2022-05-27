"""Support for interfacing with WS66i 6 zone home audio controller."""
from copy import deepcopy

from pyws66i import WS66i, ZoneStatus

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICE_RESTORE, SERVICE_SNAPSHOT
from .coordinator import Ws66iDataUpdateCoordinator
from .models import Ws66iData

PARALLEL_UPDATES = 1

MAX_VOL = 38


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WS66i 6-zone amplifier platform from a config entry."""
    ws66i_data: Ws66iData = hass.data[DOMAIN][config_entry.entry_id]

    # Build and add the entities from the data class
    async_add_entities(
        Ws66iZone(
            device=ws66i_data.device,
            ws66i_data=ws66i_data,
            entry_id=config_entry.entry_id,
            zone_id=zone_id,
            data_idx=idx,
            coordinator=ws66i_data.coordinator,
        )
        for idx, zone_id in enumerate(ws66i_data.zones)
    )

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
        "async_restore",
    )


class Ws66iZone(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a WS66i amplifier zone."""

    def __init__(
        self,
        device: WS66i,
        ws66i_data: Ws66iData,
        entry_id: str,
        zone_id: int,
        data_idx: int,
        coordinator: Ws66iDataUpdateCoordinator,
    ) -> None:
        """Initialize a zone entity."""
        super().__init__(coordinator)
        self._ws66i: WS66i = device
        self._ws66i_data: Ws66iData = ws66i_data
        self._zone_id: int = zone_id
        self._zone_id_idx: int = data_idx
        self._coordinator = coordinator
        self._snapshot: ZoneStatus = None
        self._status: ZoneStatus = coordinator.data[data_idx]
        self._attr_source_list = ws66i_data.sources.name_list
        self._attr_unique_id = f"{entry_id}_{self._zone_id}"
        self._attr_name = f"Zone {self._zone_id}"
        self._attr_supported_features = (
            MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.unique_id))},
            name=self.name,
            manufacturer="Soundavo",
            model="WS66i 6-Zone Amplifier",
        )
        self._set_attrs_from_status()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # This will be called for each of the entities after the coordinator
        # finishes executing _async_update_data()

        # Save a reference to the zone status that this entity represents
        self._status = self.coordinator.data[self._zone_id_idx]
        self._set_attrs_from_status()

        # Parent will notify HA of the update
        super()._handle_coordinator_update()

    @callback
    def _set_attrs_from_status(self) -> None:
        status = self._status
        sources = self._ws66i_data.sources.id_name
        self._attr_state = STATE_ON if status.power else STATE_OFF
        self._attr_volume_level = status.volume / float(MAX_VOL)
        self._attr_is_volume_muted = status.mute
        self._attr_source = self._attr_media_title = sources[status.source]

    @callback
    def _async_update_attrs_write_ha_state(self) -> None:
        self._set_attrs_from_status()
        self.async_write_ha_state()

    @callback
    def snapshot(self):
        """Save zone's current state."""
        self._snapshot = deepcopy(self._status)

    async def async_restore(self):
        """Restore saved state."""
        if not self._snapshot:
            raise HomeAssistantError("There is no snapshot to restore")

        await self.hass.async_add_executor_job(self._ws66i.restore_zone, self._snapshot)
        self._status = self._snapshot
        self._async_update_attrs_write_ha_state()

    async def async_select_source(self, source):
        """Set input source."""
        idx = self._ws66i_data.sources.name_id[source]
        await self.hass.async_add_executor_job(
            self._ws66i.set_source, self._zone_id, idx
        )
        self._status.source = idx
        self._async_update_attrs_write_ha_state()

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.hass.async_add_executor_job(
            self._ws66i.set_power, self._zone_id, True
        )
        self._status.power = True
        self._async_update_attrs_write_ha_state()

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.hass.async_add_executor_job(
            self._ws66i.set_power, self._zone_id, False
        )
        self._status.power = False
        self._async_update_attrs_write_ha_state()

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        await self.hass.async_add_executor_job(
            self._ws66i.set_mute, self._zone_id, mute
        )
        self._status.mute = bool(mute)
        self._async_update_attrs_write_ha_state()

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self.hass.async_add_executor_job(
            self._ws66i.set_volume, self._zone_id, int(volume * MAX_VOL)
        )
        self._status.volume = int(volume * MAX_VOL)
        self._async_update_attrs_write_ha_state()

    async def async_volume_up(self):
        """Volume up the media player."""
        await self.hass.async_add_executor_job(
            self._ws66i.set_volume, self._zone_id, min(self._status.volume + 1, MAX_VOL)
        )
        self._status.volume = min(self._status.volume + 1, MAX_VOL)
        self._async_update_attrs_write_ha_state()

    async def async_volume_down(self):
        """Volume down media player."""
        await self.hass.async_add_executor_job(
            self._ws66i.set_volume, self._zone_id, max(self._status.volume - 1, 0)
        )
        self._status.volume = max(self._status.volume - 1, 0)
        self._async_update_attrs_write_ha_state()
