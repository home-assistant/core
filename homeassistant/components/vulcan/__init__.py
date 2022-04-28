"""The Vulcan component."""
import logging

from aiohttp import ClientConnectorError
from vulcan import Account, Keystore, Vulcan
from vulcan._utils import VulcanAPIException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["calendar"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Uonet+ Vulcan integration."""
    hass.data.setdefault(DOMAIN, {})
    try:
        keystore = Keystore.load(entry.data["keystore"])
        account = Account.load(entry.data["account"])
        client = Vulcan(keystore, account)
        await client.select_student()
        students = await client.get_students()
        for student in students:
            if str(student.pupil.id) == str(entry.data["student_id"]):
                client.student = student
                break
    except VulcanAPIException as err:
        if str(err) == "The certificate is not authorized.":
            _LOGGER.error(
                "The certificate is not authorized, please authorize integration again"
            )
            raise ConfigEntryAuthFailed from err
        _LOGGER.error("Vulcan API error: %s", err)
        return False
    except ClientConnectorError as err:
        if "connection_error" not in hass.data[DOMAIN]:
            _LOGGER.error(
                "Connection error - please check your internet connection: %s", err
            )
            hass.data[DOMAIN]["connection_error"] = True
        await client.close()
        raise ConfigEntryNotReady from err
    hass.data[DOMAIN]["students_number"] = len(
        hass.config_entries.async_entries(DOMAIN)
    )
    hass.data[DOMAIN][entry.entry_id] = client

    if not entry.update_listeners:
        entry.add_update_listener(_async_update_options)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.data[DOMAIN][entry.entry_id].close()
    for platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, platform)

    return True


async def _async_update_options(hass, entry):
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
