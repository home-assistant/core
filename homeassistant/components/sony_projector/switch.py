"""Legacy switch platform shim and compatibility switch for Sony Projector."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import SonyProjectorConfigEntry
from .client import ProjectorClient, ProjectorClientError
from .const import (
    CONF_TITLE,
    DATA_YAML_ISSUE_CREATED,
    DATA_YAML_SWITCH_HOSTS,
    DEFAULT_NAME,
    DOMAIN,
    ISSUE_YAML_DEPRECATED,
)

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
    # Track that YAML switch is present for this host
    yaml_hosts: set[str] = domain_data.setdefault(DATA_YAML_SWITCH_HOSTS, set())
    if host := config.get(CONF_HOST):
        yaml_hosts.add(host)
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonyProjectorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up compatibility switch entities from a config entry.

    Adds a deprecated switch entity only when YAML configuration for the
    corresponding host is present at startup. If YAML is no longer present,
    any previously created compatibility switch is removed automatically.
    """

    domain_data = hass.data.setdefault(DOMAIN, {})
    yaml_hosts: set[str] = domain_data.get(DATA_YAML_SWITCH_HOSTS, set())
    host: str = entry.data[CONF_HOST]
    unique_id = f"{host}-switch"

    registry = er.async_get(hass)
    existing_entity_id = registry.async_get_entity_id("switch", DOMAIN, unique_id)

    if host in yaml_hosts:
        # Ensure the compatibility switch entity exists
        if existing_entity_id is None:
            async_add_entities(
                [
                    SonyProjectorCompatSwitch(
                        entry,
                        entry.runtime_data.client,
                    )
                ]
            )
    # YAML no longer present; remove any lingering compatibility switch
    elif existing_entity_id is not None:
        registry.async_remove(existing_entity_id)


class SonyProjectorCompatSwitch(SwitchEntity):
    """Deprecated compatibility switch that proxies power control.

    This entity preserves existing automations that target a switch and is
    only present when legacy YAML is detected for the host.
    """

    _attr_should_poll = True

    def __init__(
        self, entry: SonyProjectorConfigEntry, client: ProjectorClient
    ) -> None:
        """Initialize the compatibility switch entity.

        Proxies power control to the same client as the media player entity,
        keeping legacy switch-based automations working during migration.
        """
        self._entry = entry
        self._client = client
        self._identifier = entry.data[CONF_HOST]
        name = entry.data.get(CONF_TITLE, entry.title or DEFAULT_NAME)
        self._attr_name = name
        self._attr_unique_id = f"{self._identifier}-switch"
        self._attr_available = False
        self._attr_is_on: bool | None = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._identifier)},
            "manufacturer": "Sony",
            "name": name,
        }

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to hass; raise migration hint issue."""

        async_create_issue(
            self.hass,
            DOMAIN,
            f"legacy_switch_present_{self._identifier}",
            is_fixable=True,
            severity=IssueSeverity.WARNING,
            translation_key="legacy_switch_present",
            translation_placeholders={
                "switch_entity_id": self.entity_id or f"switch.{self._identifier}",
            },
            learn_more_url="https://www.home-assistant.io/integrations/sony_projector",
        )

    async def async_update(self) -> None:
        """Fetch the latest state from the projector."""

        try:
            state = await self._client.async_get_state()
        except ProjectorClientError as err:
            _LOGGER.error(
                "Failed to query projector '%s' power state: %s",
                self._identifier,
                err,
            )
            self._attr_available = False
            self._attr_is_on = None
            return

        self._attr_available = True
        self._attr_is_on = state.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the projector on."""

        await self._async_set_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the projector off."""

        await self._async_set_power(False)

    async def _async_set_power(self, powered: bool) -> None:
        try:
            await self._client.async_set_power(powered)
        except ProjectorClientError as err:
            _LOGGER.error(
                "Failed to send power command to projector '%s': %s",
                self._identifier,
                err,
            )
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_is_on = powered
