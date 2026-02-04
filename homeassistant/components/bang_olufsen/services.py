"""Services for Bang & Olufsen integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import BEOLINK_JOIN_SOURCES, DOMAIN


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    jid_regex = vol.Match(
        r"(^\d{4})[.](\d{7})[.](\d{8})(@products\.bang-olufsen\.com)$"
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "beolink_join",
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Optional("beolink_jid"): jid_regex,
            vol.Optional("source_id"): vol.In(BEOLINK_JOIN_SOURCES),
        },
        func="async_beolink_join",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "beolink_expand",
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Exclusive("all_discovered", "devices", ""): cv.boolean,
            vol.Exclusive(
                "beolink_jids",
                "devices",
                "Define either specific Beolink JIDs or all discovered",
            ): vol.All(
                cv.ensure_list,
                [jid_regex],
            ),
        },
        func="async_beolink_expand",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "beolink_unexpand",
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required("beolink_jids"): vol.All(
                cv.ensure_list,
                [jid_regex],
            ),
        },
        func="async_beolink_unexpand",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "beolink_leave",
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_beolink_leave",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "beolink_allstandby",
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_beolink_allstandby",
    )
