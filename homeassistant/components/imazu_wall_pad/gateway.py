"""Gateway of Wall Pad."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging

from wp_imazu.client import ImazuClient
from wp_imazu.packet import ImazuPacket, LightPacket, parse_packet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreStateData

from .const import DOMAIN, PACKET

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityData:
    """Data for a packet and device."""

    packet: ImazuPacket
    device: Entity | None = None


@dataclass
class PlatformData:
    """Platform entities Data."""

    entities: dict[str, EntityData]


def _parse_platform(packet: ImazuPacket) -> Platform:
    """Parse packet to platform."""
    # This platform will be added later.
    # if isinstance(packet, AwayPacket):
    #    return Platform.BINARY_SENSOR
    # if isinstance(packet, (GasPacket, OutletPacket)):
    #    return Platform.SWITCH
    # if isinstance(packet, ThermostatPacket):
    #    return Platform.CLIMATE
    if isinstance(packet, LightPacket):
        return Platform.LIGHT
    # if isinstance(packet, FanPacket):
    #    return Platform.FAN
    raise NotImplementedError()


class ImazuGateway:
    """Manages a single Imazu gateway."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Imazu gateway."""
        self._hass = hass
        self._entry = entry
        self._platforms: dict[Platform, PlatformData] = defaultdict(
            lambda: PlatformData({})
        )
        self.host: str = self._entry.data[CONF_HOST]
        self.port: int = self._entry.data[CONF_PORT]
        self._client = ImazuClient(self.host, self.port)
        self._client.async_packet_handler = self._async_packet_handler

    def entity_add_signal(self, platform: Platform) -> str:
        """Return a signal for the dispatch of a device update."""
        return f"{DOMAIN}_{self.host}_{str(platform.value)}"

    async def _async_get_entity_last_packet(self, entity_id: str) -> list[ImazuPacket]:
        """Get packet data stored for an entity, if any."""
        data = await RestoreStateData.async_get_instance(self._hass)
        if (state := data.last_states.get(entity_id, None)) is None:
            return []
        if not state.extra_data:
            return []
        if (packet := state.extra_data.as_dict().get(PACKET, None)) is None:
            return []
        return parse_packet(packet)

    def _set_entity_packet(self, platform: Platform, packet: ImazuPacket) -> EntityData:
        """Get platform entity data."""
        data = self._platforms[platform]

        if (entity := data.entities.get(packet.device_id, None)) is None:
            entity = EntityData(packet)
            data.entities[packet.device_id] = entity
        else:
            entity.packet = packet
        return entity

    async def async_load_entity_registry(self) -> None:
        """Get entity registry and put packet data to platform entities."""
        entity_registry = self._hass.helpers.entity_registry.async_get(self._hass)
        entities = self._hass.helpers.entity_registry.async_entries_for_config_entry(
            entity_registry, self._entry.entry_id
        )
        for entity in entities:
            imazu_packets = await self._async_get_entity_last_packet(entity.entity_id)
            for last_packet in imazu_packets:
                await self._async_packet_handler(last_packet)

    def get_platform_entities(self, platform: Platform) -> list[EntityData]:
        """Add platform entities."""
        data = self._platforms[platform]
        return list(data.entities.values())

    async def _async_packet_handler(self, packet: ImazuPacket) -> None:
        """Client packet handler."""
        try:
            platform = _parse_platform(packet)
            entity_data = self._set_entity_packet(platform, packet)

            if entity_data.device:
                async_dispatcher_send(
                    self._hass, f"{DOMAIN}_{self.host}_{packet.device_id}", packet
                )
            else:
                async_dispatcher_send(
                    self._hass, self.entity_add_signal(platform), entity_data
                )
        except NotImplementedError:
            _LOGGER.warning("This device is not supported, %s", packet.description())

    @property
    def connected(self) -> bool:
        """Return True if socket is connected."""
        return self._client.connected

    async def async_connect(self) -> bool:
        """Connect."""
        return await self._client.async_connect()

    async def async_send(self, packet: bytes):
        """Socket send packet."""
        await self._client.async_send(packet)

    async def async_send_wait(self, packet: bytes):
        """Socket send packet and wait response."""
        await self._client.async_send_wait(packet)

    async def async_close(self) -> None:
        """Close Gateway."""
        self._client.disconnect()
        self._platforms.clear()
