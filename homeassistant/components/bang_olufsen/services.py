"""Services for Bang & Olufsen integration."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import BEOLINK_JOIN_SOURCES, DOMAIN


class BeoService(StrEnum):
    """Store keys for Bang & Olufsen services."""

    ALLSTANDBY = "beolink_allstandby"
    EXPAND = "beolink_expand"
    JOIN = "beolink_join"
    LEAVE = "beolink_leave"
    UNEXPAND = "beolink_unexpand"


class BeoServiceArgument(StrEnum):
    """Store keys for Bang & Olufsen service arguments."""

    ALL_DISCOVERED = "all_discovered"
    JIDS = "beolink_jids"
    JID = "beolink_jid"
    SOURCE_ID = "source_id"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    jid_regex = probatio.Match(
        r"(^\d{4})[.](\d{7})[.](\d{8})(@products\.bang-olufsen\.com)$"
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BeoService.JOIN,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Optional(BeoServiceArgument.JID): jid_regex,
            probatio.Optional(BeoServiceArgument.SOURCE_ID): probatio.In(
                BEOLINK_JOIN_SOURCES
            ),
        },
        func="async_beolink_join",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BeoService.EXPAND,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Exclusive(
                BeoServiceArgument.ALL_DISCOVERED, "devices", ""
            ): cv.boolean,
            probatio.Exclusive(
                BeoServiceArgument.JIDS,
                "devices",
                "Define either specific Beolink JIDs or all discovered",
            ): probatio.All(
                probatio.EnsureList(),
                [jid_regex],
            ),
        },
        func="async_beolink_expand",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BeoService.UNEXPAND,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(BeoServiceArgument.JIDS): probatio.All(
                probatio.EnsureList(),
                [jid_regex],
            ),
        },
        func="async_beolink_unexpand",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BeoService.LEAVE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_beolink_leave",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BeoService.ALLSTANDBY,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_beolink_allstandby",
    )
