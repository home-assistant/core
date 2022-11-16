"""The sia hub."""
from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from pysiaalarm.aio import CommunicationsProtocol, SIAAccount, SIAClient, SIAEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, CONF_PROTOCOL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_IGNORE_TIMESTAMPS,
    CONF_ZONES,
    DOMAIN,
    PLATFORMS,
    SIA_EVENT,
)
from .utils import get_event_data_from_sia_event

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEBAND = (80, 40)
IGNORED_TIMEBAND = (3600, 1800)


class SIAHub:
    """Class for SIA Hubs."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Create the SIAHub."""
        self._hass: HomeAssistant = hass
        self._entry: ConfigEntry = entry
        self._port: int = entry.data[CONF_PORT]
        self._title: str = entry.title
        self._accounts: list[dict[str, Any]] = deepcopy(entry.data[CONF_ACCOUNTS])
        self._protocol: str = entry.data[CONF_PROTOCOL]
        self.sia_accounts: list[SIAAccount] | None = None
        self.sia_client: SIAClient = None

    @callback
    def async_setup_hub(self) -> None:
        """Add a device to the device_registry, register shutdown listener, load reactions."""
        self.update_accounts()
        device_registry = dr.async_get(self._hass)
        for acc in self._accounts:
            account = acc[CONF_ACCOUNT]
            device_registry.async_get_or_create(
                config_entry_id=self._entry.entry_id,
                identifiers={(DOMAIN, f"{self._port}_{account}")},
                name=f"{self._port} - {account}",
            )
        self._entry.async_on_unload(
            self._entry.add_update_listener(self.async_config_entry_updated)
        )
        self._entry.async_on_unload(
            self._hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.async_shutdown)
        )

    async def async_shutdown(self, _: Event | None = None) -> None:
        """Shutdown the SIA server."""
        await self.sia_client.stop()

    async def async_create_and_fire_event(self, event: SIAEvent) -> None:
        """Create a event on HA dispatcher and then on HA's bus, with the data from the SIAEvent.

        The created event is handled by default for only a small subset for each platform (there are about 320 SIA Codes defined, only 22 of those are used in the alarm_control_panel), a user can choose to build other automation or even entities on the same event for SIA codes not handled by the built-in platforms.

        """
        _LOGGER.debug(
            "Adding event to dispatch and bus for code %s for port %s and account %s",
            event.code,
            self._port,
            event.account,
        )
        async_dispatcher_send(
            self._hass, SIA_EVENT.format(self._port, event.account), event
        )
        self._hass.bus.async_fire(
            event_type=SIA_EVENT.format(self._port, event.account),
            event_data=get_event_data_from_sia_event(event),
        )

    def update_accounts(self):
        """Update the SIA_Accounts variable."""
        self._load_options()
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
        if self.sia_client is not None:
            self.sia_client.accounts = self.sia_accounts
            return
        self.sia_client = SIAClient(
            host="",
            port=self._port,
            accounts=self.sia_accounts,
            function=self.async_create_and_fire_event,
            protocol=CommunicationsProtocol(self._protocol),
        )

    def _load_options(self) -> None:
        """Store attributes to avoid property call overhead since they are called frequently."""
        options = dict(self._entry.options)
        for acc in self._accounts:
            acc_id = acc[CONF_ACCOUNT]
            if acc_id in options[CONF_ACCOUNTS]:
                acc[CONF_IGNORE_TIMESTAMPS] = options[CONF_ACCOUNTS][acc_id][
                    CONF_IGNORE_TIMESTAMPS
                ]
                acc[CONF_ZONES] = options[CONF_ACCOUNTS][acc_id][CONF_ZONES]

    @staticmethod
    async def async_config_entry_updated(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle signals of config entry being updated.

        First, update the accounts, this will reflect any changes with ignore_timestamps.
        Second, unload underlying platforms, and then setup platforms, this reflects any changes in number of zones.

        """
        if not (hub := hass.data[DOMAIN].get(config_entry.entry_id)):
            return
        hub.update_accounts()
        await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
