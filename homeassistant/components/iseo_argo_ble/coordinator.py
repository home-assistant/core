"""Coordinator for the users enrolled on an ISEO Argo BLE lock."""

import asyncio
import logging
from typing import TYPE_CHECKING, override

from iseo_argo_ble import IseoAuthError, IseoClient, IseoConnectionError, UserEntry

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import IseoConfigEntry

_LOGGER = logging.getLogger(__name__)

# Seconds to hold the BLE mutex after reading the user list. The lock needs a
# moment to tear the admin session down; talking to it again straight away
# makes the next operation fail.
_SETTLE_DELAY = 2


class IseoUserCoordinator(DataUpdateCoordinator[list[UserEntry]]):
    """Keeps the list of users enrolled on the lock.

    Deliberately has no update interval. Repeating an admin-authenticated
    operation on a schedule — a ten minute interval was enough — eventually
    faults recent ISEO firmware for good, and only pulling the batteries brings
    the lock back. The list is therefore read once at setup and refreshed only
    after Home Assistant itself has changed it.
    """

    config_entry: IseoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: IseoConfigEntry,
        client: IseoClient,
        ble_lock: asyncio.Lock,
    ) -> None:
        """Initialize the user coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} users",
        )
        self.client = client
        self._ble_lock = ble_lock

    @override
    async def _async_update_data(self) -> list[UserEntry]:
        """Read the users enrolled on the lock."""
        address = self.config_entry.data[CONF_ADDRESS]
        if not (
            ble_device := async_ble_device_from_address(
                self.hass, address, connectable=True
            )
        ):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"address": address},
            )

        try:
            async with self._ble_lock:
                self.client.update_ble_device(ble_device)
                users = await self.client.read_users()
                await asyncio.sleep(_SETTLE_DELAY)
        except IseoAuthError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="admin_rejected_identity",
            ) from err
        except (TimeoutError, IseoConnectionError, OSError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        return users
