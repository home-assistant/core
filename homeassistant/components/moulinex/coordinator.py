"""Coordinator for the Moulinex integration."""

from typing import override

from aiomoulinex import (
    Appliance,
    ApplianceState,
    ApplianceUpdated,
    ConnectionLost,
    ConnectionRestored,
    Event as MoulinexEvent,
    MoulinexAuthenticationError,
    MoulinexClient,
    MoulinexError,
    Region,
    Tokens,
    TokensUpdated,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_REGION, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.ssl import get_default_context

from .const import CONF_TOKENS, DOMAIN, LOGGER

type MoulinexConfigEntry = ConfigEntry[MoulinexDataUpdateCoordinator]


class MoulinexDataUpdateCoordinator(DataUpdateCoordinator[dict[str, ApplianceState]]):
    """Coordinator that receives the updates pushed by the Moulinex cloud."""

    config_entry: MoulinexConfigEntry

    def __init__(self, hass: HomeAssistant, entry: MoulinexConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, LOGGER, config_entry=entry, name=DOMAIN)
        region = Region(entry.data[CONF_REGION])
        self.manufacturer = region.brand.capitalize()
        self.client = MoulinexClient(
            async_get_clientsession(hass),
            Tokens.from_dict(entry.data[CONF_TOKENS]),
            region,
            ssl_context=get_default_context(),
        )

    @override
    async def _async_setup(self) -> None:
        """Connect to the Moulinex cloud and listen to its events."""
        self.config_entry.async_on_unload(
            self.client.add_listener(self._async_handle_event)
        )
        self.config_entry.async_on_unload(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_stop)
        )
        try:
            await self.client.connect()
        except MoulinexAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except MoulinexError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    @override
    async def _async_update_data(self) -> dict[str, ApplianceState]:
        """Return the states the client keeps up to date."""
        return self.client.states

    @override
    async def async_shutdown(self) -> None:
        """Disconnect from the Moulinex cloud."""
        await super().async_shutdown()
        await self.client.disconnect()

    async def _async_stop(self, event: Event) -> None:
        """Disconnect when Home Assistant stops, entries are not unloaded then."""
        await self.client.disconnect()

    @callback
    def _async_handle_event(self, event: MoulinexEvent) -> None:
        """Handle an event of the client."""
        match event:
            case TokensUpdated(tokens):
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_TOKENS: tokens.to_dict()},
                )
            case ConnectionLost() | ConnectionRestored():
                self.async_update_listeners()
            case ApplianceUpdated(appliance, state):
                self._async_update_firmware(appliance, state)
                self.async_set_updated_data(self.client.states)

    @callback
    def _async_update_firmware(
        self, appliance: Appliance, state: ApplianceState
    ) -> None:
        """Show a new firmware version on the device page."""
        if (version := state.shadow.firmware.ui_version) is None:
            return
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, appliance.thing_uuid), self.config_entry.entry_id
        )
        if device and device.sw_version != version:
            device_registry.async_update_device(device.id, sw_version=version)
