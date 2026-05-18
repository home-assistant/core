"""Switch platform for FritzBox VPN integration."""

import logging
from typing import Any

from fritzboxvpn import API_KEY_ACTIVE, API_KEY_NAME
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_NAME_UNKNOWN, UNIQUE_ID_SUFFIX_SWITCH
from .coordinator import FritzBoxVPNCoordinator
from .entity import (
    FritzBoxVPNEntity,
    raise_toggle_failed,
    setup_vpn_platform,
    vpn_switch_attributes,
)
from .models import FritzboxVpnConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxVpnConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FritzBox VPN switch entities."""

    def _create_entities(
        coordinator: FritzBoxVPNCoordinator, uids: set[str]
    ) -> list[FritzBoxVPNSwitch]:
        if not coordinator.data:
            return []
        return [
            FritzBoxVPNSwitch(coordinator, entry, uid, coordinator.data[uid])
            for uid in uids
            if uid in coordinator.data
        ]

    await setup_vpn_platform(
        entry,
        async_add_entities,
        platform="switch",
        create_entities=_create_entities,
    )


class FritzBoxVPNSwitch(FritzBoxVPNEntity, SwitchEntity):
    """Switch entity for a FritzBox VPN connection."""

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
            unique_id_suffix=UNIQUE_ID_SUFFIX_SWITCH,
        )
        self._attr_translation_key = "vpn"

    @property
    def is_on(self) -> bool:
        """True if the VPN connection is active."""
        conn = self._vpn_connection()
        if conn is None:
            return False
        return bool(conn.get(API_KEY_ACTIVE, False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Additional state attributes."""
        return vpn_switch_attributes(self.coordinator, self._connection_uid)

    async def _async_toggle_connection(self, enable: bool) -> None:
        """Turn VPN connection on or off; refresh coordinator afterward."""
        vpn_name = self._connection_data.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN)
        action = "on" if enable else "off"
        _LOGGER.info("Turning %s VPN connection: %s", action, vpn_name)
        try:
            success = await self.coordinator.toggle_vpn(self._connection_uid, enable)
        except Exception as err:
            raise_toggle_failed(vpn_name, str(err))
        await self.coordinator.async_request_refresh()
        if success:
            _LOGGER.info("Successfully turned %s VPN connection: %s", action, vpn_name)
            return
        raise_toggle_failed(vpn_name)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the VPN connection."""
        await self._async_toggle_connection(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the VPN connection."""
        await self._async_toggle_connection(False)
