"""Binary sensor platform for FritzBox VPN integration."""

from typing import Any

from fritzboxvpn import API_KEY_CONNECTED
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import UNIQUE_ID_SUFFIX_CONNECTED
from .coordinator import FritzBoxVPNCoordinator
from .entity import FritzBoxVPNEntity, setup_vpn_platform
from .models import FritzboxVpnConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxVpnConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FritzBox VPN binary sensor entities."""

    def _create_entities(
        coordinator: FritzBoxVPNCoordinator, uids: set[str]
    ) -> list[FritzBoxVPNConnectedBinarySensor]:
        if not coordinator.data:
            return []
        return [
            FritzBoxVPNConnectedBinarySensor(coordinator, entry, uid, coordinator.data[uid])
            for uid in uids
            if uid in coordinator.data
        ]

    await setup_vpn_platform(
        entry,
        async_add_entities,
        platform="binary_sensor",
        create_entities=_create_entities,
    )


class FritzBoxVPNConnectedBinarySensor(FritzBoxVPNEntity, BinarySensorEntity):
    """Binary sensor entity for VPN connection status."""

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        entry: FritzboxVpnConfigEntry,
        connection_uid: str,
        connection_data: dict[str, Any],
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            connection_uid,
            connection_data,
            unique_id_suffix=UNIQUE_ID_SUFFIX_CONNECTED,
        )
        self._attr_translation_key = "connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """True if the VPN connection is connected."""
        conn = self._vpn_connection()
        if conn is None:
            return False
        return bool(conn.get(API_KEY_CONNECTED, False))
