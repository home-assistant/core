"""Services for the Bose SoundTouch integration."""

from enum import StrEnum
import logging

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SoundTouchService(StrEnum):
    """Store keys for Bose SoundTouch services."""

    PLAY_EVERYWHERE = "play_everywhere"
    CREATE_ZONE = "create_zone"
    ADD_ZONE_SLAVE = "add_zone_slave"
    REMOVE_ZONE_SLAVE = "remove_zone_slave"


class SoundTouchServiceArgument(StrEnum):
    """Store keys for Bose SoundTouch service arguments."""

    MASTER = "master"
    SLAVES = "slaves"


SERVICE_PLAY_EVERYWHERE_SCHEMA = probatio.Schema(
    {probatio.Required(SoundTouchServiceArgument.MASTER): cv.entity_id}
)
SERVICE_CREATE_ZONE_SCHEMA = probatio.Schema(
    {
        probatio.Required(SoundTouchServiceArgument.MASTER): cv.entity_id,
        probatio.Required(SoundTouchServiceArgument.SLAVES): cv.entity_ids,
    }
)
SERVICE_ADD_ZONE_SCHEMA = probatio.Schema(
    {
        probatio.Required(SoundTouchServiceArgument.MASTER): cv.entity_id,
        probatio.Required(SoundTouchServiceArgument.SLAVES): cv.entity_ids,
    }
)
SERVICE_REMOVE_ZONE_SCHEMA = probatio.Schema(
    {
        probatio.Required(SoundTouchServiceArgument.MASTER): cv.entity_id,
        probatio.Required(SoundTouchServiceArgument.SLAVES): cv.entity_ids,
    }
)


async def _service_handle(service: ServiceCall) -> None:
    """Handle the applying of a service."""
    hass = service.hass
    master_id = service.data.get(SoundTouchServiceArgument.MASTER)
    slaves_ids = service.data.get(SoundTouchServiceArgument.SLAVES)
    all_media_players = [
        entry.runtime_data.media_player
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if entry.runtime_data.media_player is not None
    ]
    slaves = []
    if slaves_ids:
        slaves = [
            media_player
            for media_player in all_media_players
            if media_player.entity_id in slaves_ids
        ]

    master = next(
        iter(
            [
                media_player
                for media_player in all_media_players
                if media_player.entity_id == master_id
            ]
        ),
        None,
    )

    if master is None:
        _LOGGER.warning("Unable to find master with entity_id: %s", str(master_id))
        return

    if service.service == SoundTouchService.PLAY_EVERYWHERE:
        slaves = [
            media_player
            for media_player in all_media_players
            if media_player.entity_id != master_id
        ]
        await hass.async_add_executor_job(master.create_zone, slaves)
    elif service.service == SoundTouchService.CREATE_ZONE:
        await hass.async_add_executor_job(master.create_zone, slaves)
    elif service.service == SoundTouchService.REMOVE_ZONE_SLAVE:
        await hass.async_add_executor_job(master.remove_zone_slave, slaves)
    elif service.service == SoundTouchService.ADD_ZONE_SLAVE:
        await hass.async_add_executor_job(master.add_zone_slave, slaves)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Bose SoundTouch integration."""

    hass.services.async_register(
        DOMAIN,
        SoundTouchService.PLAY_EVERYWHERE,
        _service_handle,
        schema=SERVICE_PLAY_EVERYWHERE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SoundTouchService.CREATE_ZONE,
        _service_handle,
        schema=SERVICE_CREATE_ZONE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SoundTouchService.REMOVE_ZONE_SLAVE,
        _service_handle,
        schema=SERVICE_REMOVE_ZONE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SoundTouchService.ADD_ZONE_SLAVE,
        _service_handle,
        schema=SERVICE_ADD_ZONE_SCHEMA,
    )
