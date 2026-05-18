"""Sensor platform for FritzBox VPN integration."""

from typing import Any

from fritzboxvpn import API_KEY_UID
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    UNIQUE_ID_SUFFIX_STATUS,
    UNIQUE_ID_SUFFIX_UID,
    UNIQUE_ID_SUFFIX_VPN_UID,
    VPN_STATUS_OPTIONS,
)
from .coordinator import FritzBoxVPNCoordinator
from .entity import FritzBoxVPNEntity, setup_vpn_platform
from .models import FritzboxVpnConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxVpnConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FritzBox VPN sensor entities."""

    def _create_entities(
        coordinator: FritzBoxVPNCoordinator, uids: set[str]
    ) -> list[SensorEntity]:
        if not coordinator.data:
            return []
        entities: list[SensorEntity] = []
        for uid in uids:
            if uid not in coordinator.data:
                continue
            conn = coordinator.data[uid]
            entities.append(FritzBoxVPNStatusSensor(coordinator, entry, uid, conn))
            entities.append(FritzBoxVPNUIDSensor(coordinator, entry, uid, conn))
            entities.append(FritzBoxVPNVPNUIDSensor(coordinator, entry, uid, conn))
        return entities

    await setup_vpn_platform(
        entry,
        async_add_entities,
        platform="sensor",
        create_entities=_create_entities,
    )


class FritzBoxVPNStatusSensor(FritzBoxVPNEntity, SensorEntity):
    """Sensor entity for VPN connection status (textual)."""

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
            unique_id_suffix=UNIQUE_ID_SUFFIX_STATUS,
        )
        self._attr_translation_key = "status"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(VPN_STATUS_OPTIONS)

    @property
    def native_value(self) -> str:
        """Status as text."""
        return self.coordinator.get_vpn_status(self._connection_uid)


class FritzBoxVPNUIDSensor(FritzBoxVPNEntity, SensorEntity):
    """Sensor entity for VPN connection UID."""

    _attr_entity_registry_enabled_default = False

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
            unique_id_suffix=UNIQUE_ID_SUFFIX_UID,
        )
        self._attr_translation_key = "connection_uid"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Connection UID."""
        return self._connection_uid


class FritzBoxVPNVPNUIDSensor(FritzBoxVPNEntity, SensorEntity):
    """Sensor entity for VPN internal UID."""

    _attr_entity_registry_enabled_default = False

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
            unique_id_suffix=UNIQUE_ID_SUFFIX_VPN_UID,
        )
        self._attr_translation_key = "vpn_uid"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """VPN UID."""
        conn = self._vpn_connection()
        if conn is None:
            return ""
        return str(conn.get(API_KEY_UID, ""))
