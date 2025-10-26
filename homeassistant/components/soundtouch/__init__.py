"""The soundtouch component."""

import logging

from libsoundtouch import soundtouch_device
from libsoundtouch.device import SoundTouchDevice
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SERVICE_ADD_ZONE_SLAVE,
    SERVICE_CREATE_ZONE,
    SERVICE_PLAY_EVERYWHERE,
    SERVICE_REMOVE_ZONE_SLAVE,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_PLAY_EVERYWHERE_SCHEMA = vol.Schema({vol.Required("master"): cv.entity_id})
SERVICE_CREATE_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required("master"): cv.entity_id,
        vol.Required("slaves"): cv.entity_ids,
    }
)
SERVICE_ADD_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required("master"): cv.entity_id,
        vol.Required("slaves"): cv.entity_ids,
    }
)
SERVICE_REMOVE_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required("master"): cv.entity_id,
        vol.Required("slaves"): cv.entity_ids,
    }
)

PLATFORMS = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class SoundTouchData:
    """SoundTouch data stored in the Home Assistant data object."""

    def __init__(self, device: SoundTouchDevice) -> None:
        """Initialize the SoundTouch data object for a device."""
        self.device = device
        self.media_player = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Bose SoundTouch component."""

    async def service_handle(service: ServiceCall) -> None:
        """Handle the applying of a service."""
        master_id = service.data.get("master")
        slaves_ids = service.data.get("slaves")
        slaves = []
        if slaves_ids:
            slaves = [
                data.media_player
                for data in hass.data[DOMAIN].values()
                if data.media_player.entity_id in slaves_ids
            ]

        master = next(
            iter(
                [
                    data.media_player
                    for data in hass.data[DOMAIN].values()
                    if data.media_player.entity_id == master_id
                ]
            ),
            None,
        )

        if master is None:
            _LOGGER.warning("Unable to find master with entity_id: %s", str(master_id))
            return

        if service.service == SERVICE_PLAY_EVERYWHERE:
            slaves = [
                data.media_player
                for data in hass.data[DOMAIN].values()
                if data.media_player.entity_id != master_id
            ]
            await hass.async_add_executor_job(master.create_zone, slaves)
        elif service.service == SERVICE_CREATE_ZONE:
            await hass.async_add_executor_job(master.create_zone, slaves)
        elif service.service == SERVICE_REMOVE_ZONE_SLAVE:
            await hass.async_add_executor_job(master.remove_zone_slave, slaves)
        elif service.service == SERVICE_ADD_ZONE_SLAVE:
            await hass.async_add_executor_job(master.add_zone_slave, slaves)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_EVERYWHERE,
        service_handle,
        schema=SERVICE_PLAY_EVERYWHERE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_ZONE,
        service_handle,
        schema=SERVICE_CREATE_ZONE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_ZONE_SLAVE,
        service_handle,
        schema=SERVICE_REMOVE_ZONE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_ZONE_SLAVE,
        service_handle,
        schema=SERVICE_ADD_ZONE_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bose SoundTouch from a config entry."""
    device = await hass.async_add_executor_job(soundtouch_device, entry.data[CONF_HOST])

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = SoundTouchData(device)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
