"""Support to interface with Sonos players."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_TIME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.entity_platform import DATA_DOMAIN_PLATFORM_ENTITIES

from .const import ATTR_QUEUE_POSITION, DOMAIN
from .media_player import SonosMediaPlayerEntity
from .speaker import SonosSpeaker

SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_SET_TIMER = "set_sleep_timer"
SERVICE_CLEAR_TIMER = "clear_sleep_timer"
SERVICE_UPDATE_ALARM = "update_alarm"
SERVICE_PLAY_QUEUE = "play_queue"
SERVICE_REMOVE_FROM_QUEUE = "remove_from_queue"
SERVICE_GET_QUEUE = "get_queue"

ATTR_SLEEP_TIME = "sleep_time"
ATTR_ALARM_ID = "alarm_id"
ATTR_VOLUME = "volume"
ATTR_ENABLED = "enabled"
ATTR_INCLUDE_LINKED_ZONES = "include_linked_zones"
ATTR_WITH_GROUP = "with_group"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Sonos services."""

    @service.verify_domain_control(DOMAIN)
    async def async_service_handle(service_call: ServiceCall) -> None:
        """Handle dispatched services."""
        platform_entities = hass.data.get(DATA_DOMAIN_PLATFORM_ENTITIES, {}).get(
            (MEDIA_PLAYER_DOMAIN, DOMAIN), {}
        )

        entities = await service.async_extract_entities(
            platform_entities.values(), service_call
        )

        if not entities:
            return

        speakers: list[SonosSpeaker] = []
        for entity in entities:
            assert isinstance(entity, SonosMediaPlayerEntity)
            speakers.append(entity.speaker)

        config_entry = speakers[0].config_entry  # All speakers share the same entry

        if service_call.service == SERVICE_SNAPSHOT:
            await SonosSpeaker.snapshot_multi(
                hass, config_entry, speakers, service_call.data[ATTR_WITH_GROUP]
            )
        elif service_call.service == SERVICE_RESTORE:
            await SonosSpeaker.restore_multi(
                hass, config_entry, speakers, service_call.data[ATTR_WITH_GROUP]
            )

    join_unjoin_schema = cv.make_entity_service_schema(
        {vol.Optional(ATTR_WITH_GROUP, default=True): cv.boolean}
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SNAPSHOT, async_service_handle, join_unjoin_schema
    )

    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE, async_service_handle, join_unjoin_schema
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_SLEEP_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=86399)
            )
        },
        func="set_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="clear_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UPDATE_ALARM,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_ALARM_ID): cv.positive_int,
            vol.Optional(ATTR_TIME): cv.time,
            vol.Optional(ATTR_VOLUME): cv.small_float,
            vol.Optional(ATTR_ENABLED): cv.boolean,
            vol.Optional(ATTR_INCLUDE_LINKED_ZONES): cv.boolean,
        },
        func="set_alarm",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PLAY_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Optional(ATTR_QUEUE_POSITION): cv.positive_int},
        func="play_queue",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_REMOVE_FROM_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Optional(ATTR_QUEUE_POSITION): cv.positive_int},
        func="remove_from_queue",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="get_queue",
        supports_response=SupportsResponse.ONLY,
    )
