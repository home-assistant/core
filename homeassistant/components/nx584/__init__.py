"""Support for NX584 alarm control panels."""

from dataclasses import dataclass

from nx584 import client
import requests
from yarl import URL

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]

INTEGRATION_TITLE = "NX584"


@dataclass
class NX584Data:
    """Runtime data for a nx584 config entry."""

    client: client.Client


type NX584ConfigEntry = ConfigEntry[NX584Data]


async def async_setup_entry(hass: HomeAssistant, entry: NX584ConfigEntry) -> bool:
    """Set up nx584 from a config entry."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    url = str(URL.build(scheme="http", host=host, port=port))
    alarm_client = client.Client(url)

    try:
        await hass.async_add_executor_job(alarm_client.list_zones)
    except requests.exceptions.ConnectionError as ex:
        raise ConfigEntryNotReady(f"Unable to connect to {url}") from ex

    entry.runtime_data = NX584Data(client=alarm_client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NX584ConfigEntry) -> bool:
    """Unload a nx584 config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_import_yaml_config(hass: HomeAssistant, config: ConfigType) -> None:
    """Trigger the config entry import flow for a YAML platform config.

    Shared by the binary_sensor and alarm_control_panel platforms, which both
    support importing their YAML configuration into a config entry.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue",
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
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )
