"""Support to interface with Sonos players."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .media_player import SonosMediaPlayerEntity
from .speaker import SonosSpeaker


class SonosService(StrEnum):
    """Store keys for Sonos services."""

    SNAPSHOT = "snapshot"
    RESTORE = "restore"
    SET_SLEEP_TIMER = "set_sleep_timer"
    CLEAR_SLEEP_TIMER = "clear_sleep_timer"
    PLAY_QUEUE = "play_queue"
    REMOVE_FROM_QUEUE = "remove_from_queue"
    GET_QUEUE = "get_queue"
    UPDATE_ALARM = "update_alarm"


class SonosServiceArgument(StrEnum):
    """Store keys for Sonos service arguments."""

    WITH_GROUP = "with_group"
    SLEEP_TIME = "sleep_time"
    QUEUE_POSITION = "queue_position"
    ALARM_ID = "alarm_id"
    TIME = "time"
    VOLUME = "volume"
    ENABLED = "enabled"
    INCLUDE_LINKED_ZONES = "include_linked_zones"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Sonos services."""

    async def async_handle_snapshot_restore(
        entities: list[SonosMediaPlayerEntity], service_call: ServiceCall
    ) -> None:
        """Handle snapshot and restore services."""
        speakers = [entity.speaker for entity in entities]
        config_entry = speakers[0].config_entry  # All speakers share the same entry

        if service_call.service == SonosService.SNAPSHOT:
            await SonosSpeaker.snapshot_multi(
                hass,
                config_entry,
                speakers,
                service_call.data[SonosServiceArgument.WITH_GROUP],
            )
        elif service_call.service == SonosService.RESTORE:
            await SonosSpeaker.restore_multi(
                hass,
                config_entry,
                speakers,
                service_call.data[SonosServiceArgument.WITH_GROUP],
            )

    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        SonosService.SNAPSHOT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Optional(SonosServiceArgument.WITH_GROUP, default=True): cv.boolean
        },
        func=async_handle_snapshot_restore,
    )

    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        SonosService.RESTORE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Optional(SonosServiceArgument.WITH_GROUP, default=True): cv.boolean
        },
        func=async_handle_snapshot_restore,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SonosService.SET_SLEEP_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(SonosServiceArgument.SLEEP_TIME): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=86399)
            )
        },
        func="set_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SonosService.CLEAR_SLEEP_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="clear_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SonosService.UPDATE_ALARM,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(SonosServiceArgument.ALARM_ID): cv.positive_int,
            probatio.Optional(SonosServiceArgument.TIME): cv.time,
            probatio.Optional(SonosServiceArgument.VOLUME): cv.small_float,
            probatio.Optional(SonosServiceArgument.ENABLED): cv.boolean,
            probatio.Optional(SonosServiceArgument.INCLUDE_LINKED_ZONES): cv.boolean,
        },
        func="set_alarm",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SonosService.PLAY_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Optional(SonosServiceArgument.QUEUE_POSITION): cv.positive_int
        },
        func="play_queue",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SonosService.REMOVE_FROM_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Optional(SonosServiceArgument.QUEUE_POSITION): cv.positive_int
        },
        func="remove_from_queue",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SonosService.GET_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="get_queue",
        supports_response=SupportsResponse.ONLY,
    )
