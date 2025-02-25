"""The decora_wifi component."""

import logging

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.iot_switch import IotSwitch
from decora_wifi.models.permission import Permission
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    session = DecoraWiFiSession()
    user = await hass.async_add_executor_job(session.login, username, password)
    if not user:
        raise ConfigEntryError("could not authenticate")

    hass.data[DOMAIN][entry.entry_id] = session

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def logout(event: Event) -> None:
        if session is not None:
            try:
                Person.logout(session)
            except ValueError as err:
                _LOGGER.error("Failed to log out of myLeviton Service: %s", err)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.pop(DOMAIN)
    return unload_ok


class DecoraWifiAsyncClient:
    """A thin wrapper to make async calls more readable."""

    def __init__(self, session: DecoraWiFiSession, hass: HomeAssistant) -> None:
        """DecoraWifiAsyncClient."""
        self.session = session
        self.hass = hass

    async def get_permissions(self) -> list[Permission]:
        """Get all permissions for the provided session."""
        assert self.session.user
        return await self.hass.async_add_executor_job(
            self.session.user.get_residential_permissions
        )

    async def get_residences(self, permissions: list[Permission]) -> list[Residence]:
        """Get all residences for the provided permissions."""
        return await self.hass.async_add_executor_job(self._get_residences, permissions)

    def _get_residences(self, permissions: list[Permission]) -> list[Residence]:
        """Get all residences for the provided permissions."""
        residences: list[Residence] = []
        for perm in permissions:
            if perm.residentialAccountId is not None:
                account = ResidentialAccount(self.session, perm.residentialAccountId)
                residences.extend(account.get_residences())
            elif perm.residenceId is not None:
                residences.append(Residence(self.session, perm.residenceId))
        return residences

    async def get_iot_switches(self, residences: list[Residence]) -> list[IotSwitch]:
        """Get all the iot switches for the provided residences."""
        return await self.hass.async_add_executor_job(
            self._get_iot_switches, residences
        )

    def _get_iot_switches(self, residences: list[Residence]) -> list[IotSwitch]:
        return [sw for res in residences for sw in (res.get_iot_switches())]
