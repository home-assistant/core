"""Support for Satel Integra devices."""

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.typing import ConfigType

from .client import SatelClient
from .const import (
    CONF_ARM_HOME_MODE,
    CONF_DEVICE_PARTITIONS,
    CONF_OUTPUT_NUMBER,
    CONF_OUTPUTS,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_SWITCHABLE_OUTPUTS,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DEFAULT_CONF_ARM_HOME_MODE,
    DEFAULT_PORT,
    DEFAULT_ZONE_TYPE,
    DOMAIN,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
)
from .coordinator import (
    SatelConfigEntry,
    SatelIntegraData,
    SatelIntegraOutputsCoordinator,
    SatelIntegraPartitionsCoordinator,
    SatelIntegraZonesCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.SWITCH]


ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_ZONE_TYPE, default=DEFAULT_ZONE_TYPE): cv.string,
    }
)
EDITABLE_OUTPUT_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})
PARTITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_ARM_HOME_MODE, default=DEFAULT_CONF_ARM_HOME_MODE): vol.In(
            [1, 2, 3]
        ),
    }
)


def is_alarm_code_necessary(value):
    """Check if alarm code must be configured."""
    if value.get(CONF_SWITCHABLE_OUTPUTS) and CONF_CODE not in value:
        raise vol.Invalid("You need to specify alarm code to use switchable_outputs")

    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_CODE): cv.string,
                vol.Optional(CONF_DEVICE_PARTITIONS, default={}): {
                    vol.Coerce(int): PARTITION_SCHEMA
                },
                vol.Optional(CONF_ZONES, default={}): {vol.Coerce(int): ZONE_SCHEMA},
                vol.Optional(CONF_OUTPUTS, default={}): {vol.Coerce(int): ZONE_SCHEMA},
                vol.Optional(CONF_SWITCHABLE_OUTPUTS, default={}): {
                    vol.Coerce(int): EDITABLE_OUTPUT_SCHEMA
                },
            },
            is_alarm_code_necessary,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up  Satel Integra from YAML."""

    if config := hass_config.get(DOMAIN):
        hass.async_create_task(_async_import(hass, config))

    return True


async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Process YAML import."""

    if not hass.config_entries.async_entries(DOMAIN):
        # Start import flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )

        if result.get("type") == FlowResultType.ABORT:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "deprecated_yaml_import_issue_cannot_connect",
                breaks_in_ha_version="2026.4.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_cannot_connect",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Satel Integra",
                },
            )
            return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.4.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Satel Integra",
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: SatelConfigEntry) -> bool:
    """Set up  Satel Integra from a config entry."""

    client = SatelClient(hass, entry)

    coordinator_zones = SatelIntegraZonesCoordinator(hass, entry, client)
    coordinator_outputs = SatelIntegraOutputsCoordinator(hass, entry, client)
    coordinator_partitions = SatelIntegraPartitionsCoordinator(hass, entry, client)

    await client.async_connect(
        coordinator_zones.zones_update_callback,
        coordinator_outputs.outputs_update_callback,
        coordinator_partitions.partitions_update_callback,
    )

    entry.runtime_data = SatelIntegraData(
        client=client,
        coordinator_zones=coordinator_zones,
        coordinator_outputs=coordinator_outputs,
        coordinator_partitions=coordinator_partitions,
    )
    entry.async_on_unload(entry.add_update_listener(update_listener))

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Satel",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SatelConfigEntry) -> bool:
    """Unloading the Satel platforms."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        runtime_data = entry.runtime_data
        runtime_data.client.close()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: SatelConfigEntry) -> None:
    """Handle options update."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SatelConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    # 1.2 Migrate subentries to include configured numbers to title
    if config_entry.version == 1 and config_entry.minor_version == 1:
        for subentry in config_entry.subentries.values():
            property_map = {
                SUBENTRY_TYPE_PARTITION: CONF_PARTITION_NUMBER,
                SUBENTRY_TYPE_ZONE: CONF_ZONE_NUMBER,
                SUBENTRY_TYPE_OUTPUT: CONF_OUTPUT_NUMBER,
                SUBENTRY_TYPE_SWITCHABLE_OUTPUT: CONF_SWITCHABLE_OUTPUT_NUMBER,
            }

            new_title = f"{subentry.title} ({subentry.data[property_map[subentry.subentry_type]]})"

            hass.config_entries.async_update_subentry(
                config_entry, subentry, title=new_title
            )

        hass.config_entries.async_update_entry(config_entry, minor_version=2)

    # 2.1 Migrate all entity unique IDs to replace "satel" prefix with config entry ID, allows multiple entries to be configured
    if config_entry.version == 1:

        @callback
        def migrate_unique_id(entity_entry: RegistryEntry) -> dict[str, str]:
            """Migrate the unique ID to a new format."""
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    "satel", config_entry.entry_id
                )
            }

        await async_migrate_entries(hass, config_entry.entry_id, migrate_unique_id)
        hass.config_entries.async_update_entry(config_entry, version=2, minor_version=1)

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
