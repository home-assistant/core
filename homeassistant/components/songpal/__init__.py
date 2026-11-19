"""The songpal component."""

import asyncio
from typing import Any

import probatio

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ENDPOINT, DOMAIN
from .services import async_setup_services

SONGPAL_CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME): cv.string,
        probatio.Required(CONF_ENDPOINT): cv.string,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Optional(DOMAIN): probatio.All(
            probatio.EnsureList(), [SONGPAL_CONFIG_SCHEMA]
        )
    },
    extra=probatio.ALLOW_EXTRA,
)

PLATFORMS = [Platform.MEDIA_PLAYER]

INTEGRATION_TITLE = "Sony Songpal"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up songpal environment."""
    async_setup_services(hass)

    if (conf := config.get(DOMAIN)) is None:
        return True
    hass.async_create_task(_async_import_yaml(hass, conf))
    return True


async def _async_import_yaml(
    hass: HomeAssistant, import_data: list[dict[str, Any]]
) -> None:
    """Import the YAML devices into config entries."""
    # Eager tasks register the import flows before setup waits for them.
    results = await asyncio.gather(
        *(
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=data
                )
            )
            for data in import_data
        )
    )
    failed_reasons = {
        result["reason"]
        for result in results
        if result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    }
    for reason in failed_reasons:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}",
            breaks_in_ha_version="2027.6.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
    # The shared issue tells users to remove all YAML, which would drop failed devices.
    if failed_reasons:
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up songpal media player."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload songpal media player."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
