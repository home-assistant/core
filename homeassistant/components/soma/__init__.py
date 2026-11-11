"""Support for Soma Smartshades."""

from dataclasses import dataclass
from typing import Any

from api.soma_api import SomaApi
import probatio

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, HOST, PORT

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_HOST): cv.string,
                probatio.Required(CONF_PORT): cv.string,
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)

INTEGRATION_TITLE = "Soma Connect"


@dataclass
class SomaData:
    """Runtime data for the Soma integration."""

    api: SomaApi
    devices: list[dict[str, Any]]


type SomaConfigEntry = ConfigEntry[SomaData]

PLATFORMS = [Platform.COVER, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Soma component."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(_async_import_yaml(hass, config[DOMAIN]))

    return True


async def _async_import_yaml(hass: HomeAssistant, import_data: dict[str, Any]) -> None:
    """Import the YAML configuration and raise a deprecation issue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=import_data,
    )

    if result["type"] is FlowResultType.ABORT and result["reason"] != "already_setup":
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2027.6.0",
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


async def async_setup_entry(hass: HomeAssistant, entry: SomaConfigEntry) -> None:
    """Set up Soma from a config entry."""

    def _setup_api() -> tuple[SomaApi, dict[str, Any]]:
        api = SomaApi(entry.data[HOST], entry.data[PORT])
        return api, api.list_devices()

    api, devices = await hass.async_add_executor_job(_setup_api)
    entry.runtime_data = SomaData(api, devices["shades"])

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SomaConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
