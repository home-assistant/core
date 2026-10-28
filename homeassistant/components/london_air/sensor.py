"""Sensor for checking the status of London air."""

from datetime import datetime
import logging
from typing import Any, override

import probatio
from pylondonair import (
    NO_SPECIES_DATA,
    LondonAirClient,
    LondonAirConnectionError,
    LondonAirData,
    LondonAirUpdateError,
    Site,
)

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import AUTHORITIES, CONF_LOCATIONS, DOMAIN, INTEGRATION_TITLE, SCAN_INTERVAL

BREAKS_IN_HA_VERSION = "2027.6.0"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_LOCATIONS, default=AUTHORITIES): probatio.All(
            probatio.EnsureList(), [probatio.In(AUTHORITIES)]
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the London Air sensor platform from YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result["type"] is FlowResultType.ABORT
        and (reason := result["reason"]) != "single_instance_allowed"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}",
            breaks_in_ha_version=BREAKS_IN_HA_VERSION,
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
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[APIData],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up London Air sensors from a config entry."""
    api_data = entry.runtime_data
    async_add_entities(
        (AirSensor(name, api_data) for name in entry.data[CONF_LOCATIONS]),
        update_before_add=True,
    )


class APIData:
    """Get the latest data for all authorities."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the AirData object."""
        self._client = LondonAirClient(session=async_get_clientsession(hass))
        self.data: LondonAirData | None = None
        self._last_update: datetime | None = None

    async def async_update(self) -> None:
        """Get the latest data from the API, at most once per scan interval."""
        now = dt_util.utcnow()
        if self._last_update is not None and now - self._last_update <= SCAN_INTERVAL:
            return
        self._last_update = now
        try:
            self.data = await self._client.async_update()
        except LondonAirConnectionError as err:
            _LOGGER.warning("Could not connect to London Air API: %s", err)
        except LondonAirUpdateError as err:
            _LOGGER.warning("Invalid response from London Air API: %s", err)


class AirSensor(SensorEntity):
    """Single authority air sensor."""

    _attr_icon = "mdi:cloud-outline"

    def __init__(self, name: str, api_data: APIData) -> None:
        """Initialize the sensor."""
        self._attr_name = self._key = name
        self._api_data = api_data
        self._site_data: list[dict[str, Any]] | None = None
        self._updated: str | None = None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return other details about the sensor state."""
        attrs: dict[str, Any] = {}
        attrs["updated"] = self._updated
        attrs["sites"] = len(self._site_data) if self._site_data is not None else 0
        attrs["data"] = self._site_data
        return attrs

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._api_data.async_update()
        data = self._api_data.data
        if data is None:
            self._attr_native_value = None
            return
        authority = data.authorities.get(self._key)
        sites = authority.sites if authority is not None else ()
        self._site_data = [_site_to_dict(site) for site in sites]
        self._updated = (
            sites[0].updated.strftime("%Y-%m-%d %H:%M:%S") if sites else None
        )
        self._attr_native_value = authority.status if authority is not None else None


def _site_to_dict(site: Site) -> dict[str, Any]:
    """Convert a library site into the attribute dict format."""
    pollutants: list[dict[str, str] | str] = [
        {
            "description": pollutant.description,
            "code": pollutant.code,
            "quality": pollutant.quality,
            "index": pollutant.index,
            "summary": pollutant.summary,
        }
        for pollutant in site.pollutants
    ]
    if not pollutants:
        pollutants = [NO_SPECIES_DATA]
    return {
        "updated": site.updated.strftime("%Y-%m-%d %H:%M:%S"),
        "latitude": site.latitude,
        "longitude": site.longitude,
        "site_code": site.site_code,
        "site_name": site.site_name,
        "site_type": site.site_type,
        "pollutants": pollutants,
        "pollutants_status": site.status,
        "number_of_pollutants": site.number_of_pollutants,
    }
