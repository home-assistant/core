"""Support for EcoNet products."""

import asyncio
from datetime import timedelta
import logging

from aiohttp.client_exceptions import ClientError
from pyeconet import EcoNetApiInterface
from pyeconet.equipment import EquipmentType
from pyeconet.errors import (
    GenericHTTPError,
    InvalidCredentialsError,
    InvalidResponseFormat,
    PyeconetError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import API_CLIENT, DOMAIN, EQUIPMENT, PUSH_UPDATE

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

INTERVAL = timedelta(minutes=60)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up EcoNet as config entry."""

    email = config_entry.data[CONF_EMAIL]
    password = config_entry.data[CONF_PASSWORD]

    try:
        api = await EcoNetApiInterface.login(email, password=password)
    except InvalidCredentialsError:
        _LOGGER.error("Invalid credentials provided")
        return False
    except PyeconetError as err:
        _LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    try:
        equipment = await api.get_equipment_by_type(
            [EquipmentType.WATER_HEATER, EquipmentType.THERMOSTAT]
        )
    except (ClientError, GenericHTTPError, InvalidResponseFormat) as err:
        raise ConfigEntryNotReady from err
    hass.data.setdefault(DOMAIN, {API_CLIENT: {}, EQUIPMENT: {}})
    hass.data[DOMAIN][API_CLIENT][config_entry.entry_id] = api
    hass.data[DOMAIN][EQUIPMENT][config_entry.entry_id] = equipment

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    api.subscribe()

    def update_published():
        """Handle a push update."""
        dispatcher_send(hass, PUSH_UPDATE)

    for _eqip in equipment[EquipmentType.WATER_HEATER]:
        _eqip.set_update_callback(update_published)

    for _eqip in equipment[EquipmentType.THERMOSTAT]:
        _eqip.set_update_callback(update_published)

    async def resubscribe(now):
        """Resubscribe to the MQTT updates."""
        await hass.async_add_executor_job(api.unsubscribe)
        api.subscribe()

        # Refresh values
        await asyncio.sleep(60)
        await api.refresh_equipment()

    config_entry.async_on_unload(async_track_time_interval(hass, resubscribe, INTERVAL))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a EcoNet config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][API_CLIENT].pop(entry.entry_id)
        hass.data[DOMAIN][EQUIPMENT].pop(entry.entry_id)
    return unload_ok
