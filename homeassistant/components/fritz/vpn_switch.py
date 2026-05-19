"""WireGuard VPN switches for FRITZ!Box Tools."""

from __future__ import annotations

import logging
from typing import Any

from fritzboxvpn import API_KEY_ACTIVE, API_KEY_NAME, API_KEY_UID

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VPN_MODEL_WIREGUARD, VPN_UNIQUE_ID_SUFFIX_SWITCH
from .coordinator import AvmWrapper, FritzConfigEntry
from .vpn_coordinator import FritzVpnCoordinator
from .vpn_data import FritzVpnEntryData, vpn_entry_data

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


def _vpn_unique_id(avm_unique_id: str, connection_uid: str) -> str:
    """Entity unique_id for a WireGuard VPN switch."""
    return f"{avm_unique_id}-{connection_uid}-{VPN_UNIQUE_ID_SUFFIX_SWITCH}"


def _vpn_device_info(
    avm: AvmWrapper, connection_uid: str, connection: dict[str, Any]
) -> DeviceInfo:
    """Device registry entry for one WireGuard VPN connection."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{avm.unique_id}_vpn_{connection_uid}")},
        name=connection.get(API_KEY_NAME, connection_uid),
        manufacturer="FRITZ!",
        model=VPN_MODEL_WIREGUARD,
        via_device={(DOMAIN, avm.unique_id)},
        configuration_url=f"http://{avm.host}",
        connections={(CONNECTION_NETWORK_MAC, avm.mac)},
    )


class FritzVpnSwitch(CoordinatorEntity[FritzVpnCoordinator], SwitchEntity):
    """Switch to enable or disable a WireGuard VPN connection."""

    _attr_has_entity_name = True
    _attr_translation_key = "wireguard_vpn"

    def __init__(
        self,
        avm: AvmWrapper,
        vpn_data: FritzVpnEntryData,
        connection_uid: str,
        connection: dict[str, Any],
    ) -> None:
        """Initialize the VPN switch."""
        super().__init__(vpn_data.coordinator)
        self._avm = avm
        self._connection_uid = connection_uid
        self._connection = connection
        self._attr_unique_id = _vpn_unique_id(avm.unique_id, connection_uid)
        self._attr_device_info = _vpn_device_info(avm, connection_uid, connection)

    @property
    def available(self) -> bool:
        """Return True when this VPN connection is present in coordinator data."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        return self._connection_uid in self.coordinator.data

    @property
    def is_on(self) -> bool:
        """Return True when the VPN connection is enabled."""
        conn = (
            self.coordinator.data.get(self._connection_uid)
            if self.coordinator.data
            else None
        )
        if conn is None:
            return False
        return bool(conn.get(API_KEY_ACTIVE, False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return VPN connection attributes."""
        conn = (
            self.coordinator.data.get(self._connection_uid)
            if self.coordinator.data
            else None
        )
        if conn is None:
            return {}
        return {
            API_KEY_NAME: conn.get(API_KEY_NAME),
            "uid": self._connection_uid,
            "vpn_uid": conn.get(API_KEY_UID),
            API_KEY_ACTIVE: conn.get(API_KEY_ACTIVE, False),
            API_KEY_CONNECTED: conn.get(API_KEY_CONNECTED, False),
            "status": self.coordinator.get_vpn_status(self._connection_uid),
        }

    async def _async_toggle(self, enable: bool) -> None:
        """Turn the VPN connection on or off."""
        vpn_name = self._connection.get(API_KEY_NAME, self._connection_uid)
        action = "on" if enable else "off"
        _LOGGER.info("Turning %s WireGuard VPN connection: %s", action, vpn_name)
        try:
            success = await self.coordinator.async_toggle_vpn(
                self._connection_uid, enable
            )
        except Exception as err:
            _LOGGER.exception("Failed to toggle WireGuard VPN: %s", vpn_name)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vpn_toggle_failed",
                translation_placeholders={"name": vpn_name, "error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vpn_toggle_failed",
                translation_placeholders={"name": vpn_name, "error": ""},
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the VPN connection."""
        await self._async_toggle(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the VPN connection."""
        await self._async_toggle(False)


def _create_vpn_switches(
    avm: AvmWrapper, vpn_data: FritzVpnEntryData, uids: set[str]
) -> list[FritzVpnSwitch]:
    """Build switch entities for the given connection UIDs."""
    coordinator = vpn_data.coordinator
    if not coordinator.data:
        return []
    return [
        FritzVpnSwitch(avm, vpn_data, uid, coordinator.data[uid])
        for uid in uids
        if uid in coordinator.data
    ]


async def async_setup_vpn_switches(
    hass: HomeAssistant,
    entry: FritzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WireGuard VPN switch entities for a FRITZ!Box Tools entry."""
    vpn_data = vpn_entry_data(hass, entry.entry_id)
    if vpn_data is None:
        return

    avm = entry.runtime_data
    coordinator = vpn_data.coordinator
    known_uids = vpn_data.known_uids

    if coordinator.data:
        initial_uids = set(coordinator.data)
        known_uids.update(initial_uids)
        async_add_entities(
            _create_vpn_switches(avm, vpn_data, initial_uids), update_before_add=True
        )

    async def _add_new_entities() -> None:
        async with vpn_data.lock:
            current = set(coordinator.data) if coordinator.data else set()
            new_uids = current - known_uids
            if not new_uids:
                return
            entities = _create_vpn_switches(avm, vpn_data, new_uids)
            if not entities:
                return
            known_uids.update(new_uids)
            async_add_entities(entities)
            _LOGGER.info(
                "Added %d WireGuard VPN switch(es) for %s",
                len(entities),
                entry.title,
            )

    def _on_coordinator_update() -> None:
        hass.async_create_task(_add_new_entities())

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))
