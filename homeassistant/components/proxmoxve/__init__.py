"""Support for Proxmox VE."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import ProxmoxConfigEntry, ProxmoxCoordinator

PLATFORMS = [Platform.BINARY_SENSOR]


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(CONF_REALM, default=DEFAULT_REALM): cv.string,
                        vol.Optional(
                            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                        ): cv.boolean,
                        vol.Required(CONF_NODES): vol.All(
                            cv.ensure_list,
                            [
                                vol.Schema(
                                    {
                                        vol.Required(CONF_NODE): cv.string,
                                        vol.Optional(CONF_VMS, default=[]): [
                                            cv.positive_int
                                        ],
                                        vol.Optional(CONF_CONTAINERS, default=[]): [
                                            cv.positive_int
                                        ],
                                    }
                                )
                            ],
                        ),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import the Proxmox configuration from YAML."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(_async_setup(hass, config))

    return True


async def _async_setup(hass: HomeAssistant, config: ConfigType) -> None:
    for entry_config in config[DOMAIN]:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=entry_config,
        )
        if (
            result.get("type") is FlowResultType.ABORT
            and result.get("reason") != "already_configured"
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{result.get('reason')}",
                breaks_in_ha_version="2026.8.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Proxmox VE",
                },
            )
            return

        ir.async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2026.8.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Proxmox VE",
            },
        )


async def async_setup_entry(hass: HomeAssistant, entry: ProxmoxConfigEntry) -> bool:
    """Set up a ProxmoxVE from a config entry."""
    coordinator = ProxmoxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ProxmoxConfigEntry) -> bool:
    """Migrate old config entries."""

    # Migration for only the old binary sensors to new unique_id format
    if entry.version < 2:
        ent_reg = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            new_unique_id = (
                f"{entry.entry_id}_{entity_entry.unique_id.split('_')[-2]}_status"
            )

            _LOGGER.debug(
                "Migrating entity %s from old unique_id %s to new unique_id %s",
                entity_entry.entity_id,
                entity_entry.unique_id,
                new_unique_id,
            )
            ent_reg.async_update_entity(
                entity_entry.entity_id, new_unique_id=new_unique_id
            )

        hass.config_entries.async_update_entry(entry, version=2)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ProxmoxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
