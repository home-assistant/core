"""Legacy switch platform shim for Sony Projector."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_YAML_ISSUE_CREATED, DEFAULT_NAME, DOMAIN, ISSUE_YAML_DEPRECATED

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Trigger migration of YAML switch entries to config entries."""

    _LOGGER.warning(
        "The 'switch' platform for sony_projector is deprecated. The configuration "
        "will be imported into the UI"
    )

    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get(DATA_YAML_ISSUE_CREATED):
        async_create_issue(
            hass,
            DOMAIN,
            ISSUE_YAML_DEPRECATED,
            is_fixable=False,
            learn_more_url="https://www.home-assistant.io/integrations/sony_projector",
            severity=IssueSeverity.WARNING,
            translation_key="yaml_deprecated",
        )
        domain_data[DATA_YAML_ISSUE_CREATED] = True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: config.get(CONF_HOST),
                CONF_NAME: config.get(CONF_NAME, DEFAULT_NAME),
            },
        )
    )

    async_add_entities([])


class DeprecatedSonyProjectorSwitch(SwitchEntity):
    """Placeholder entity kept for backward compatibility."""

    @property
    def should_poll(self) -> bool:
        """Switch entities were removed; this entity never polls."""

        return False
