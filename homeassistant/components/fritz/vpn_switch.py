"""WireGuard VPN switches for FRITZ!Box Tools."""

import logging
from typing import Any

from fritzboxvpn import API_KEY_ACTIVE, API_KEY_CONNECTED, API_KEY_NAME, API_KEY_UID

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
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
    return f"{avm_unique_id}-{connection_uid}-{VPN_UNIQUE_ID_SUFFIX_SWITCH}"


def _vpn_device_info(
    avm: AvmWrapper, connection_uid: str, connection: dict[str, Any]
) -> DeviceInfo:
    scheme = "https" if avm.use_tls else "http"
    return DeviceInfo(
        identifiers={(DOMAIN, f"{avm.unique_id}_vpn_{connection_uid}")},
        name=connection.get(API_KEY_NAME, connection_uid),
        manufacturer="FRITZ!",
        model=VPN_MODEL_WIREGUARD,
        via_device=(DOMAIN, avm.unique_id),
        configuration_url=f"{scheme}://{avm.host}",
        connections={(CONNECTION_NETWORK_MAC, avm.mac)},
    )


class FritzVpnSwitch(CoordinatorEntity[FritzVpnCoordinator], SwitchEntity):
    """Switch entity for a WireGuard VPN connection."""

    _attr_has_entity_name = True
    _attr_translation_key = "wireguard_vpn"

    def __init__(
        self,
        avm: AvmWrapper,
        vpn_data: FritzVpnEntryData,
        connection_uid: str,
        connection: dict[str, Any],
    ) -> None:
        """Initialize the WireGuard VPN switch."""
        super().__init__(vpn_data.coordinator)
        self._connection_uid = connection_uid
        self._connection = connection
        self._vpn_name = connection.get(API_KEY_NAME, connection_uid)
        self._attr_unique_id = _vpn_unique_id(avm.unique_id, connection_uid)
        self._attr_device_info = _vpn_device_info(avm, connection_uid, connection)

    @property
    def available(self) -> bool:
        """Return True when the VPN connection is present in coordinator data."""
        if not self.coordinator.last_update_success:
            return False
        return (
            self.coordinator.data is not None
            and self._connection_uid in self.coordinator.data
        )

    @property
    def is_on(self) -> bool:
        """Return True when the VPN connection is active."""
        if not self.coordinator.data:
            return False
        conn = self.coordinator.data.get(self._connection_uid)
        return bool(conn.get(API_KEY_ACTIVE, False)) if conn else False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return VPN connection state attributes."""
        if not self.coordinator.data:
            return {}
        conn = self.coordinator.data.get(self._connection_uid)
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
        try:
            success = await self.coordinator.async_toggle_vpn(
                self._connection_uid, enable
            )
        except Exception as err:
            _LOGGER.exception("Failed to toggle WireGuard VPN: %s", self._vpn_name)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vpn_toggle_failed",
                translation_placeholders={
                    "name": self._vpn_name,
                    "error": f": {err}",
                },
            ) from err
        await self.coordinator.async_request_refresh()
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="vpn_toggle_failed",
                translation_placeholders={"name": self._vpn_name, "error": ""},
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the VPN connection on."""
        await self._async_toggle(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the VPN connection off."""
        await self._async_toggle(False)


def _create_vpn_switches(
    avm: AvmWrapper, vpn_data: FritzVpnEntryData, uids: set[str]
) -> list[FritzVpnSwitch]:
    if not vpn_data.coordinator.data:
        return []
    data = vpn_data.coordinator.data
    return [
        FritzVpnSwitch(avm, vpn_data, uid, data[uid]) for uid in uids if uid in data
    ]


async def async_setup_vpn_switches(
    hass: HomeAssistant,
    entry: FritzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WireGuard VPN switch entities for a config entry."""
    vpn_data = vpn_entry_data(hass, entry.entry_id)
    if vpn_data is None:
        return

    avm = entry.runtime_data
    coordinator = vpn_data.coordinator

    if coordinator.data:
        initial_uids = set(coordinator.data)
        vpn_data.known_uids.update(initial_uids)
        async_add_entities(
            _create_vpn_switches(avm, vpn_data, initial_uids), update_before_add=True
        )

    async def _sync_vpn_entities() -> None:
        async with vpn_data.lock:
            current = set(coordinator.data) if coordinator.data else set()
            vpn_data.known_uids &= current
            new_uids = current - vpn_data.known_uids
            if not new_uids:
                return
            entities = _create_vpn_switches(avm, vpn_data, new_uids)
            if not entities:
                return
            vpn_data.known_uids.update(new_uids)
            async_add_entities(entities)

    @callback
    def _handle_coordinator_update() -> None:
        hass.async_create_task(_sync_vpn_entities())

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
