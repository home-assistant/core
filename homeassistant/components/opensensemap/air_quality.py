"""Support for openSenseMap Air Quality data."""

from datetime import timedelta

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError
import voluptuous as vol

from homeassistant.components.air_quality import (
    PLATFORM_SCHEMA as AIR_QUALITY_PLATFORM_SCHEMA,
    AirQualityEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import OpenSenseMapConfigEntry
from .const import (
    CONF_STATION_ID,
    DEPRECATED_YAML_BREAKS_IN_VERSION,
    DOMAIN,
    INTEGRATION_TITLE,
    KNOWN_IMPORT_ABORT_REASONS,
    LOGGER,
)

SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = AIR_QUALITY_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_STATION_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import legacy YAML configuration into a config entry."""
    # Keep the legacy platform entry point so existing YAML is migrated into a
    # config entry instead of adding entities directly from YAML.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] in KNOWN_IMPORT_ABORT_REASONS
    ):
        # Per-reason issue conveys the deprecation notice itself, so don't also
        # raise the generic deprecated_yaml issue on top of it.
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version=DEPRECATED_YAML_BREAKS_IN_VERSION,
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

    # "deprecated_yaml" translation key lives under the "homeassistant" core domain.
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=DEPRECATED_YAML_BREAKS_IN_VERSION,
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
    entry: OpenSenseMapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the openSenseMap air quality entity from a config entry."""
    async_add_entities(
        [
            OpenSenseMapQuality(
                entry.runtime_data, entry.data[CONF_STATION_ID], entry.title
            )
        ]
    )


class OpenSenseMapQuality(AirQualityEntity):
    """Implementation of an openSenseMap air quality entity."""

    _attr_attribution = "Data provided by openSenseMap"

    def __init__(self, api: OpenSenseMap, station_id: str, name: str) -> None:
        """Initialize the air quality entity."""
        self._api = api
        self._attr_name = name
        self._attr_unique_id = station_id

    @property
    def particulate_matter_2_5(self) -> float | None:
        """Return the particulate matter 2.5 level."""
        return self._api.pm2_5

    @property
    def particulate_matter_10(self) -> float | None:
        """Return the particulate matter 10 level."""
        return self._api.pm10

    async def async_update(self) -> None:
        """Fetch latest data from the openSenseMap API."""
        try:
            await self._api.get_data()
        except OpenSenseMapError as err:
            LOGGER.warning("Unable to fetch data from openSenseMap: %s", err)
            self._attr_available = False
        else:
            self._attr_available = True
