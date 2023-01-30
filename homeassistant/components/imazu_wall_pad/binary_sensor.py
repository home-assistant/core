"""Binary Sensor platform for Imazu Wall Pad integration."""
from wp_imazu.client import ImazuClient
from wp_imazu.packet import AwayPacket, ImazuPacket

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ImazuGateway
from .const import BRAND_NAME, DOMAIN
from .gateway import EntityData
from .helper import host_to_last
from .wall_pad import WallPadDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Imazu Wall Pad config entry."""
    gateway: ImazuGateway = hass.data[DOMAIN].get(config_entry.entry_id)

    @callback
    def async_add_entity(data: EntityData):
        if data.device:
            return

        if isinstance(data.packet, AwayPacket):
            if "power" in data.packet.state:
                data.device = WPAwayLight(
                    gateway.client, Platform.BINARY_SENSOR, data.packet
                )
            elif "valve" in data.packet.state:
                data.device = WPAwayGasValve(
                    gateway.client, Platform.BINARY_SENSOR, data.packet
                )

        if data.device:
            async_add_entities([data.device])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, gateway.entity_add_signal(Platform.BINARY_SENSOR), async_add_entity
        )
    )
    gateway.add_platform_entities(Platform.BINARY_SENSOR)


class WPAwayLight(WallPadDevice[AwayPacket], BinarySensorEntity):
    """Representation of a Wall Pad away light."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(
        self, client: ImazuClient, platform: Platform, packet: ImazuPacket
    ) -> None:
        """Set up switch."""
        super().__init__(client, platform, packet)

        self._attr_should_poll = False

        self.entity_id = (
            f"{str(platform.value)}."
            f"{BRAND_NAME}_{host_to_last(self.client.host)}_"
            f"{self.packet.name.lower()}_light_{packet.room_id}"
        )
        self._attr_name = f"{BRAND_NAME} {packet.name} Light {packet.room_id}".title()

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        if not self.available:
            return False

        return self.packet.state["power"] == AwayPacket.Power.ON

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return "mdi:lightbulb-group" if self.is_on else "mdi:lightbulb-group-outline"


class WPAwayGasValve(WallPadDevice[AwayPacket], BinarySensorEntity):
    """Representation of a Wall Pad away gas valve."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self, client: ImazuClient, platform: Platform, packet: ImazuPacket
    ) -> None:
        """Set up switch."""
        super().__init__(client, platform, packet)

        self._attr_should_poll = False

        self.entity_id = (
            f"{str(platform.value)}."
            f"{BRAND_NAME}_{host_to_last(self.client.host)}_"
            f"{self.packet.name.lower()}_gas_{packet.room_id}"
        )
        self._attr_name = f"{BRAND_NAME} {packet.name} Gas {packet.room_id}".title()

    @property
    def is_on(self) -> bool:
        """Return true if gas valve is open."""
        if not self.available:
            return False

        return self.packet.state["valve"] == AwayPacket.Valve.OPEN

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return "mdi:valve-open" if self.is_on else "mdi:valve-closed"
