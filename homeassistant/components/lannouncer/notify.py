"""Lannouncer platform for notify component."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "lannouncer"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Get the Lannouncer notification service."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        DOMAIN,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="integration_removed",
    )
