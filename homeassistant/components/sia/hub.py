"""The sia hub."""
from __future__ import annotations

import logging
from typing import Any

from pysiaalarm.aio import CommunicationsProtocol, SIAAccount, SIAClient, SIAEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, CONF_PROTOCOL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, EventOrigin, HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_IGNORE_TIMESTAMPS,
    DOMAIN,
    SIA_EVENT,
)

DEFAULT_TIMEBAND = (80, 40)
IGNORED_TIMEBAND = (3600, 1800)

_LOGGER = logging.getLogger(__name__)


class SIAHub:
    """Class for SIA Hubs."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ):
        """Create the SIAHub."""
        self._hass: HomeAssistant = hass
        self._entry: ConfigEntry = entry
        self._port: int = int(entry.data[CONF_PORT])
        self._title: str = entry.title
        self._accounts: list[dict[str, Any]] = entry.data[CONF_ACCOUNTS]
        self._protocol: str = entry.data[CONF_PROTOCOL]
        self.sia_accounts: list[SIAAccount] | None = None
        self.sia_client: SIAClient = None

    async def async_setup_hub(self) -> None:
        """Add a device to the device_registry, register shutdown listener, load reactions."""
        self.sia_accounts = [
            SIAAccount(
                account_id=a[CONF_ACCOUNT],
                key=a.get(CONF_ENCRYPTION_KEY),
                allowed_timeband=IGNORED_TIMEBAND
                if a[CONF_IGNORE_TIMESTAMPS]
                else DEFAULT_TIMEBAND,
            )
            for a in self._accounts
        ]
        self.sia_client = SIAClient(
            host="",
            port=self._port,
            accounts=self.sia_accounts,
            function=self.async_create_and_fire_event,
            protocol=CommunicationsProtocol(self._protocol),
        )
        device_registry = await dr.async_get_registry(self._hass)
        for acc in self._accounts:
            account = acc[CONF_ACCOUNT]
            device_registry.async_get_or_create(
                config_entry_id=self._entry.entry_id,
                identifiers={(DOMAIN, f"{self._port}_{account}")},
                name=f"{self._port} - {account}",
            )
        self._entry.async_on_unload(
            self._hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.async_shutdown)
        )

    async def async_shutdown(self, _: Event = None) -> None:
        """Shutdown the SIA server."""
        await self.sia_client.stop()  # type: ignore

    async def async_create_and_fire_event(self, event: SIAEvent) -> None:  # type: ignore
        """Create a event on HA's bus, with the data from the SIAEvent.

        The created event is handled by default for only a small subset for each platform (there are about 320 SIA Codes defined, only 22 of those are used in the alarm_control_panel), a user can choose to build other automation or even entities on the same event for SIA codes not handled by the built-in platforms.

        """
        _LOGGER.debug(
            "Adding event to bus for code %s for port %s and account %s",
            event.code,
            self._port,
            event.account,
        )
        self._hass.bus.async_fire(
            event_type=SIA_EVENT.format(self._port, event.account),
            event_data=event.to_dict(encode_json=True),
            origin=EventOrigin.remote,
        )
