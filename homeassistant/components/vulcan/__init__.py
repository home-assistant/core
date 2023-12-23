"""The Vulcan component."""
import sys

from aiohttp import ClientConnectorError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

if sys.version_info < (3, 12):
    from vulcan import Account, Keystore, UnauthorizedCertificateException, Vulcan

PLATFORMS = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Uonet+ Vulcan integration."""
    if sys.version_info >= (3, 12):
        raise HomeAssistantError(
            "Uonet+ Vulcan is not supported on Python 3.12. Please use Python 3.11."
        )
    hass.data.setdefault(DOMAIN, {})
    try:
        keystore = Keystore.load(entry.data["keystore"])
        account = Account.load(entry.data["account"])
        client = Vulcan(keystore, account, async_get_clientsession(hass))
        await client.select_student()
        students = await client.get_students()
        for student in students:
            if str(student.pupil.id) == str(entry.data["student_id"]):
                client.student = student
                break
    except UnauthorizedCertificateException as err:
        raise ConfigEntryAuthFailed("The certificate is not authorized.") from err
    except ClientConnectorError as err:
        raise ConfigEntryNotReady(
            f"Connection error - please check your internet connection: {err}"
        ) from err
    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
