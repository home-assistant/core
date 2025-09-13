"""Media players for Savant Home Automation."""

import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry media players."""
    coordinator = config.runtime_data
    match config.data["type"]:
        case "Audio":
            players: list[SavantPlayer] = [
                SavantAudioPlayer(coordinator, int(output))
                for output in config.data["outputs"]
            ]
        case "Video":
            players = [
                SavantVideoPlayer(coordinator, int(output))
                for output in config.data["outputs"]
            ]
        case _:
            raise ConfigEntryError
    async_add_entities(players)
    coordinator.players = players

    info = coordinator.info

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config.entry_id,
        connections={(DOMAIN, info["savantID"])},
        identifiers={(DOMAIN, info["savantID"])},
        manufacturer="Savant",
        name=config.data["name"],
        model_id=info["chassis"].upper(),
        sw_version=info["firmwareVersion"],
        configuration_url=f"http://{config.data['ip']}",
    )


class SavantPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player for a single output of a Savant matrix."""

    _attr_supported_features = (
        # MediaPlayerEntityFeature.TURN_ON
        # |
        MediaPlayerEntityFeature.TURN_OFF | MediaPlayerEntityFeature.SELECT_SOURCE
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator, port):
        """Create a SavantPlayer setting the context to the port index."""
        super().__init__(coordinator, context=port)
        self.port = port

    @property
    def unique_id(self):
        """The unique id of the sensor - uses the savantID of the coordinator and the port index."""
        return f"{self.coordinator.info['savantID']}_{self.port}"

    @property
    def source_list(self):
        """All of the enabled (i.e. named) inputs to the matrix."""
        return list(self.coordinator.inputs.values())

    @property
    def device_info(self):
        """Defined a device per zone and links to the device for the switch."""
        return dr.DeviceInfo(
            identifiers={
                (DOMAIN, f"{self.coordinator.info['savantID']}.output{self.port}")
            },
            via_device=(DOMAIN, self.coordinator.info["savantID"]),
            name=f"{self.coordinator.name} {self.coordinator.outputs[str(self.port)]}",
        )

    async def async_select_source(self, source):
        """Set the input to the desired source."""
        assert source in self.source_list
        source_port = self.coordinator.input_ids[source]
        await self.coordinator.api.set_input(self.port, source_port)
        logger.info("%s source set to %s (%s)", self.name, source, source_port)

    async def async_turn_off(self):
        """Disconnect all sources."""
        await self.coordinator.api.set_input(self.port, 0)
        logger.info("%s turned off", self.name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if data is None:
            self._attr_available = False
        else:
            self._attr_available = True
            port_data = data[self.port]
            logger.debug("%s got data %s from coordinator", self.name, port_data)
            self._attr_state = MediaPlayerState[port_data["state"]]
            self._attr_source = port_data["source"]

        self.async_write_ha_state()


class SavantAudioPlayer(SavantPlayer):
    """Provides additional functionality for audio matrices, e.g. volume."""

    @property
    def supported_features(self):
        """Add support for setting and muting volume."""
        return (
            super().supported_features
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        data = self.coordinator.data
        if data is not None:
            port_data = data[self.port]
            self._attr_is_volume_muted = port_data["other"]["mute"]
            raw_volume = int(port_data["other"]["volume"])
            self._attr_volume_level = (raw_volume + 117) / 127

        self.async_write_ha_state()

    async def async_mute_volume(self, mute):
        """Send a mute command to the switch."""
        await self.coordinator.api.mute(self.port, mute)

    async def async_set_volume_level(self, volume):
        """Set the switch volume - scaled from 0 to 100 to -117 dB to 10 dB."""
        raw_volume = int(volume * 127 - 117)
        await self.coordinator.api.set_property(self.port, "volume", raw_volume)


class SavantVideoPlayer(SavantPlayer):
    """Provides additional functionality for video matrices."""
