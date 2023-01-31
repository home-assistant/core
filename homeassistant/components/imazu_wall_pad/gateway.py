"""Gateway of Wall Pad."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from wp_imazu.client import ImazuClient
from wp_imazu.packet import (
    AwayPacket,
    FanPacket,
    GasPacket,
    ImazuPacket,
    LightPacket,
    OutletPacket,
    ThermostatPacket,
    parse_packet,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.restore_state import RestoreStateData

from .const import DOMAIN, PACKET, PLATFORMS
from .wall_pad import WallPadDevice

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityData:
    """Data for a packet and device."""

    packet: ImazuPacket | None = None
    device: WallPadDevice | None = None


@dataclass
class PlatformData:
    """Platform entities Data."""

    entities: dict[str, EntityData]


def _parse_platform(packet: ImazuPacket) -> None | Platform:
    """Parse packet to platform."""
    if isinstance(packet, AwayPacket):
        return Platform.BINARY_SENSOR
    if isinstance(packet, (GasPacket, OutletPacket)):
        return Platform.SWITCH
    if isinstance(packet, ThermostatPacket):
        return Platform.CLIMATE
    if isinstance(packet, LightPacket):
        return Platform.LIGHT
    # if isinstance(packet, AcPacket):
    #    return Platform.FAN
    if isinstance(packet, FanPacket):
        return Platform.FAN
    return None


class ImazuGateway:
    """Manages a single Imazu gateway."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Imazu gateway."""
        self.hass = hass
        self.entry = entry
        self.host = self.entry.data.get(CONF_HOST)
        self.port = self.entry.data.get(CONF_PORT)
        self.client = ImazuClient(self.host, self.port, self.async_packet_handler)
        self.platforms: dict[Platform, PlatformData] = {
            platform: PlatformData({}) for platform in PLATFORMS
        }

    def entity_add_signal(self, platform: Platform) -> str:
        """Return a signal for the dispatch of a device update."""
        return f"{DOMAIN}_{self.host}_{str(platform.value)}"

    async def _async_get_entity_last_packet(self, entity_id: str) -> list[ImazuPacket]:
        """Get packet data stored for an entity, if any."""
        data = await RestoreStateData.async_get_instance(self.hass)
        if entity_id not in data.last_states:
            return []
        state = data.last_states[entity_id]
        if (
            not state.extra_data
            or (packet := state.extra_data.as_dict().get(PACKET, None)) is None
        ):
            return []
        return parse_packet(packet)

    def _get_entity_data(self, platform: Platform, packet: ImazuPacket) -> EntityData:
        """Get platform entity data."""
        data = self.platforms[platform]

        if (entity := data.entities.get(packet.device_id, None)) is None:
            entity = EntityData()
            data.entities[packet.device_id] = entity
        return entity

    async def async_load_entity_registry(self):
        """Get entity registry and put packet data to platform entities."""
        entity_registry = self.hass.helpers.entity_registry.async_get(self.hass)
        entities = self.hass.helpers.entity_registry.async_entries_for_config_entry(
            entity_registry, self.entry.entry_id
        )
        for entity in entities:
            imazu_packets = await self._async_get_entity_last_packet(entity.entity_id)
            for packet in imazu_packets:
                if (platform := _parse_platform(packet)) is None:
                    _LOGGER.warning(
                        "This device is not supported, %s", packet.description()
                    )
                    continue
                entity_data = self._get_entity_data(platform, packet)
                entity_data.packet = packet

    def add_platform_entities(self, platform: Platform) -> bool:
        """Add platform entities."""
        data = self.platforms[platform]

        entity_added = False
        for entity_data in data.entities.values():
            if not entity_data.packet or entity_data.device:
                continue
            async_dispatcher_send(
                self.hass, self.entity_add_signal(platform), entity_data
            )
            entity_added = True
        return entity_added

    async def async_packet_handler(self, packet: ImazuPacket):
        """Client packet handler."""
        if (platform := _parse_platform(packet)) is None:
            _LOGGER.warning("This device is not supported, %s", packet.description())
            return

        @callback
        def async_platform_packet_handler():
            """Platform packet handler."""
            entity_data = self._get_entity_data(platform, packet)
            entity_data.packet = packet

            if entity_data.device:
                async_dispatcher_send(
                    self.hass, f"{DOMAIN}_{self.host}_{packet.device_id}", packet
                )
            else:
                async_dispatcher_send(
                    self.hass, self.entity_add_signal(platform), entity_data
                )

        async_platform_packet_handler()

    async def async_connect(self) -> bool:
        """Connect."""
        return await self.client.async_connect()

    async def async_close(self):
        """Close Gateway."""
        self.client.disconnect()
        self.platforms.clear()
