"""The bluesound component."""

from pyblu import Player

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_HOSTS,
    CONF_PLATFORM,
    CONF_PORT,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, INTEGRATION_TITLE
from .media_player import DATA_BLUESOUND, setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Import config entry from configuration.yaml."""
    if not hass.config_entries.async_entries(DOMAIN):
        # Start import flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        if result["type"] == FlowResultType.ABORT:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{result['reason']}",
                breaks_in_ha_version="2025.1.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": INTEGRATION_TITLE,
                },
            )
            return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.1.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bluesound."""
    setup_services(hass)

    platform_config = config.get(Platform.MEDIA_PLAYER, {})
    for platform_config_entry in platform_config:
        if platform_config_entry[CONF_PLATFORM] != DOMAIN:
            continue

        hosts = platform_config_entry.get(CONF_HOSTS, [])
        for host in hosts:
            import_data = {CONF_HOST: host[CONF_HOST], CONF_PORT: host.get(CONF_PORT, 11000)}
            hass.async_create_task(_async_import(hass, import_data))

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Bluesound entry."""
    host = config_entry.data.get(CONF_HOST)
    port = config_entry.data.get(CONF_PORT)
    try:
        async with Player(host, port) as player:
            await player.sync_status(timeout=1)
    except TimeoutError as ex:
        raise ConfigEntryNotReady(f"Timeout while connecting to {host}:{port}") from ex

    await hass.config_entries.async_forward_entry_setup(
        config_entry, Platform.MEDIA_PLAYER
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    player = None
    for player in hass.data[DATA_BLUESOUND]:
        if player.unique_id == config_entry.unique_id:
            break

    if player is None:
        return False

    player.stop_polling()
    hass.data[DATA_BLUESOUND].remove(player)

    return await hass.config_entries.async_unload_platforms(config_entry, Platform.MEDIA_PLAYER)
