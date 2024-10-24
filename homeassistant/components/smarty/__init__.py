"""Support to control a Salda Smarty XP/XV ventilation unit."""

from datetime import timedelta
import ipaddress
import logging

from pysmarty2 import Smarty
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SIGNAL_UPDATE_SMARTY

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
                vol.Optional(CONF_NAME, default="Smarty"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.FAN, Platform.SENSOR]

type SmartyConfigEntry = ConfigEntry[Smarty]


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Create a smarty system."""
    if config := hass_config.get(DOMAIN):
        hass.async_create_task(_async_import(hass, config))
    return True


async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Set up the smarty environment."""

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
                breaks_in_ha_version="2025.5.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Smarty",
                },
            )
            return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Smarty",
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: SmartyConfigEntry) -> bool:
    """Set up the Smarty environment from a config entry."""

    def _setup_smarty() -> Smarty:
        smarty = Smarty(host=entry.data[CONF_HOST])
        smarty.update()
        return smarty

    smarty = await hass.async_add_executor_job(_setup_smarty)

    entry.runtime_data = smarty

    async def poll_device_update(event_time) -> None:
        """Update Smarty device."""
        _LOGGER.debug("Updating Smarty device")
        if await hass.async_add_executor_job(smarty.update):
            _LOGGER.debug("Update success")
            async_dispatcher_send(hass, SIGNAL_UPDATE_SMARTY)
        else:
            _LOGGER.debug("Update failed")

    entry.async_on_unload(
        async_track_time_interval(hass, poll_device_update, timedelta(seconds=30))
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
