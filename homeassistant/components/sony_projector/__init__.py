"""The Sony Projector integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .client import ProjectorClient
from .const import (
    CONF_TITLE,
    DATA_YAML_ISSUE_CREATED,
    DATA_YAML_SWITCH_HOSTS,
    DEFAULT_NAME,
    DOMAIN,
    ISSUE_YAML_DEPRECATED,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.SWITCH]


@dataclass(slots=True)
class SonyProjectorRuntimeData:
    """Runtime data stored for each config entry."""

    client: ProjectorClient


type SonyProjectorConfigEntry = ConfigEntry[SonyProjectorRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sony Projector integration from YAML."""

    domain_data = hass.data.setdefault(DOMAIN, {})

    # Track any legacy YAML switch entries for compatibility switch support
    if switch_configs := config.get(Platform.SWITCH.value):
        yaml_hosts: set[str] = domain_data.setdefault(DATA_YAML_SWITCH_HOSTS, set())
        for entry in switch_configs:
            if entry.get("platform") == DOMAIN and (host := entry.get(CONF_HOST)):
                yaml_hosts.add(host)

    if media_configs := config.get(Platform.MEDIA_PLAYER.value):
        _async_create_yaml_issue(hass, domain_data)
        for entry in media_configs:
            if entry.get("platform") != DOMAIN:
                continue
            host = entry.get(CONF_HOST)
            if not host:
                _LOGGER.warning(
                    "Skipping sony_projector media player import because host is missing"
                )
                continue

            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_HOST: host,
                        CONF_NAME: entry.get(CONF_NAME),
                    },
                )
            )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: SonyProjectorConfigEntry
) -> bool:
    """Set up Sony Projector from a config entry."""

    data = SonyProjectorRuntimeData(
        client=ProjectorClient(entry.data[CONF_HOST]),
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    entry.runtime_data = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    device_registry = dr.async_get(hass)
    identifier = entry.data[CONF_HOST]
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, identifier)},
        manufacturer="Sony",
        name=entry.data.get(CONF_TITLE, entry.title or DEFAULT_NAME),
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SonyProjectorConfigEntry
) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


def _async_create_yaml_issue(hass: HomeAssistant, domain_data: dict[str, Any]) -> None:
    """Surface a repairs issue warning users about deprecated YAML."""

    if domain_data.get(DATA_YAML_ISSUE_CREATED):
        return

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
