"""Backward compatible switch platform for Sony Projector."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Trigger migration of YAML switch entries to config entries."""

    _LOGGER.warning(
        "The 'switch' platform for sony_projector is deprecated. The configuration will "
        "be imported into the UI"
    )

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
