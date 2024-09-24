"""Support for a Genius Hub system."""

from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
from geniushubclient import GeniusHub
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.service import verify_domain_control
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=60)

MAC_ADDRESS_REGEXP = r"^([0-9A-F]{2}:){5}([0-9A-F]{2})$"

CLOUD_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_MAC): vol.Match(MAC_ADDRESS_REGEXP),
    }
)


LOCAL_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MAC): vol.Match(MAC_ADDRESS_REGEXP),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Any(LOCAL_API_SCHEMA, CLOUD_API_SCHEMA)}, extra=vol.ALLOW_EXTRA
)

ATTR_ZONE_MODE = "mode"
ATTR_DURATION = "duration"

SVC_SET_ZONE_MODE = "set_zone_mode"
SVC_SET_ZONE_OVERRIDE = "set_zone_override"

SET_ZONE_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_ZONE_MODE): vol.In(["off", "timer", "footprint"]),
    }
)
SET_ZONE_OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_TEMPERATURE): vol.All(
            vol.Coerce(float), vol.Range(min=4, max=28)
        ),
        vol.Optional(ATTR_DURATION): vol.All(
            cv.time_period,
            vol.Range(min=timedelta(minutes=5), max=timedelta(days=1)),
        ),
    }
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]


async def _async_import(hass: HomeAssistant, base_config: ConfigType) -> None:
    """Import a config entry from configuration.yaml."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=base_config[DOMAIN],
    )
    if (
        result["type"] is FlowResultType.CREATE_ENTRY
        or result["reason"] == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.12.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Genius Hub",
            },
        )
        return
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_import_issue_{result['reason']}",
        breaks_in_ha_version="2024.12.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Genius Hub",
        },
    )


async def async_setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up a Genius Hub system."""
    if DOMAIN in base_config:
        hass.async_create_task(_async_import(hass, base_config))
    return True


type GeniusHubConfigEntry = ConfigEntry[GeniusBroker]


async def async_setup_entry(hass: HomeAssistant, entry: GeniusHubConfigEntry) -> bool:
    """Create a Genius Hub system."""

    session = async_get_clientsession(hass)
    if CONF_HOST in entry.data:
        client = GeniusHub(
            entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=session,
        )
    else:
        client = GeniusHub(entry.data[CONF_TOKEN], session=session)

    unique_id = entry.unique_id or entry.entry_id

    broker = entry.runtime_data = GeniusBroker(
        hass, client, entry.data.get(CONF_MAC, unique_id)
    )

    try:
        await client.update()
    except aiohttp.ClientResponseError as err:
        _LOGGER.error("Setup failed, check your configuration, %s", err)
        return False
    broker.make_debug_log_entries()

    async_track_time_interval(hass, broker.async_update, SCAN_INTERVAL)

    setup_service_functions(hass, broker)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


@callback
def setup_service_functions(hass: HomeAssistant, broker):
    """Set up the service functions."""

    @verify_domain_control(hass, DOMAIN)
    async def set_zone_mode(call: ServiceCall) -> None:
        """Set the system mode."""
        entity_id = call.data[ATTR_ENTITY_ID]

        registry = er.async_get(hass)
        registry_entry = registry.async_get(entity_id)

        if registry_entry is None or registry_entry.platform != DOMAIN:
            raise ValueError(f"'{entity_id}' is not a known {DOMAIN} entity")

        if registry_entry.domain != "climate":
            raise ValueError(f"'{entity_id}' is not an {DOMAIN} zone")

        payload = {
            "unique_id": registry_entry.unique_id,
            "service": call.service,
            "data": call.data,
        }

        async_dispatcher_send(hass, DOMAIN, payload)

    hass.services.async_register(
        DOMAIN, SVC_SET_ZONE_MODE, set_zone_mode, schema=SET_ZONE_MODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SVC_SET_ZONE_OVERRIDE, set_zone_mode, schema=SET_ZONE_OVERRIDE_SCHEMA
    )


class GeniusBroker:
    """Container for geniushub client and data."""

    def __init__(self, hass: HomeAssistant, client: GeniusHub, hub_uid: str) -> None:
        """Initialize the geniushub client."""
        self.hass = hass
        self.client = client
        self.hub_uid = hub_uid
        self._connect_error = False

    async def async_update(self, now, **kwargs) -> None:
        """Update the geniushub client's data."""
        try:
            await self.client.update()
            if self._connect_error:
                self._connect_error = False
                _LOGGER.warning("Connection to geniushub re-established")
        except (
            aiohttp.ClientResponseError,
            aiohttp.client_exceptions.ClientConnectorError,
        ) as err:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error(
                    "Connection to geniushub failed (unable to update), message is: %s",
                    err,
                )
            return
        self.make_debug_log_entries()

        async_dispatcher_send(self.hass, DOMAIN)

    def make_debug_log_entries(self) -> None:
        """Make any useful debug log entries."""
        _LOGGER.debug(
            "Raw JSON: \n\nclient._zones = %s \n\nclient._devices = %s",
            self.client._zones,  # noqa: SLF001
            self.client._devices,  # noqa: SLF001
        )
