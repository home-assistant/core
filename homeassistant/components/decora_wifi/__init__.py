"""The Leviton Decora Wi-Fi integration."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.iot_switch import IotSwitch
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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

PLATFORMS = [Platform.LIGHT]

type DecoraWifiConfigEntry = ConfigEntry[DecoraWifiData]


@dataclass
class DecoraWifiData:
    """Runtime data for the Decora Wi-Fi integration."""

    session: DecoraWiFiSession
    switches: list[IotSwitch]


def _login_and_get_switches(email: str, password: str) -> DecoraWifiData:
    """Log in and fetch all IoT switches. Runs in executor."""
    session = DecoraWiFiSession()
    success = session.login(email, password)

    if success is None:
        raise ConfigEntryAuthFailed("Invalid credentials for myLeviton account")

    perms = session.user.get_residential_permissions()
    all_switches: list[IotSwitch] = []
    for permission in perms:
        if permission.residentialAccountId is not None:
            acct = ResidentialAccount(session, permission.residentialAccountId)
            all_switches.extend(
                switch
                for residence in acct.get_residences()
                for switch in residence.get_iot_switches()
            )
        elif permission.residenceId is not None:
            residence = Residence(session, permission.residenceId)
            all_switches.extend(residence.get_iot_switches())

    return DecoraWifiData(session, all_switches)


async def async_setup_entry(hass: HomeAssistant, entry: DecoraWifiConfigEntry) -> bool:
    """Set up Leviton Decora Wi-Fi from a config entry."""
    try:
        data = await hass.async_add_executor_job(
            _login_and_get_switches,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )
    except ValueError as err:
        raise ConfigEntryNotReady(
            "Failed to communicate with myLeviton service"
        ) from err

    entry.runtime_data = data

    async def _logout(_: Event | None = None) -> None:
        with suppress(ValueError):
            await hass.async_add_executor_job(Person.logout, data.session)

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _logout))
    entry.async_on_unload(_logout)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DecoraWifiConfigEntry) -> bool:
    """Unload a Decora Wi-Fi config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
