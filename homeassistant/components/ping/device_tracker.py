"""Tracks devices by sending a ICMP echo request (ping)."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    SourceType,
)
from homeassistant.components.device_tracker.config_entry import BaseTrackerEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_HOSTS,
    CONF_NAME,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PingDomainData
from .const import CONF_IMPORTED_BY, CONF_PING_COUNT, DOMAIN
from .entity import BasePingEntity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOSTS): {cv.slug: cv.string},
        vol.Optional(CONF_PING_COUNT, default=1): cv.positive_int,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Legacy init: import via config flow."""

    for dev_name, dev_host in config[CONF_HOSTS].items():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_IMPORTED_BY: "device_tracker",
                    CONF_NAME: dev_name,
                    CONF_HOST: dev_host,
                    CONF_PING_COUNT: config[CONF_PING_COUNT],
                },
            )
        )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Ping",
        },
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Ping config entry."""

    data: PingDomainData = hass.data[DOMAIN]

    async_add_entities([PingDeviceTracker(entry, data.coordinators[entry.entry_id])])


class PingDeviceTracker(BasePingEntity, BaseTrackerEntity):
    """Representation of a Ping device tracker."""

    @property
    def source_type(self) -> SourceType:
        """Return the source type which is router."""
        return SourceType.ROUTER

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self.coordinator.data.is_alive:
            return STATE_HOME
        return STATE_NOT_HOME

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        if CONF_IMPORTED_BY in self.config_entry.data:
            return bool(self.config_entry.data[CONF_IMPORTED_BY] == "device_tracker")
        return False
