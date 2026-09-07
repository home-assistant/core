"""Support for Lupusec Home Security system."""

from json import JSONDecodeError
import logging

import lupupy
from lupupy.exceptions import LupusecException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "lupusec_notification"
NOTIFICATION_TITLE = "Lupusec Security Setup"


PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

type LupusecConfigEntry = ConfigEntry[lupupy.Lupusec]


async def async_setup_entry(hass: HomeAssistant, entry: LupusecConfigEntry) -> bool:
    """Set up this integration using UI."""

    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        lupusec_system = await hass.async_add_executor_job(
            lupupy.Lupusec, username, password, host
        )
    except LupusecException:
        _LOGGER.error("Failed to connect to Lupusec device at %s", host)
        return False
    except JSONDecodeError:
        _LOGGER.error("Failed to connect to Lupusec device at %s", host)
        return False

    entry.runtime_data = lupusec_system

    alarm = await hass.async_add_executor_job(lupusec_system.get_alarm)

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=alarm.name,
        manufacturer="Lupus Electronics",
        model=f"Lupusec-XT{lupusec_system.model}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
