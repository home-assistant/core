"""Support for the World Air Quality Index service."""
from __future__ import annotations

import logging

from aiowaqi import WAQIAuthenticationError, WAQIClient, WAQIConnectionError
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_TEMPERATURE,
    ATTR_TIME,
    CONF_API_KEY,
    CONF_NAME,
    CONF_TOKEN,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STATION_NUMBER, DOMAIN, ISSUE_PLACEHOLDER
from .coordinator import WAQIDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_DOMINENTPOL = "dominentpol"
ATTR_HUMIDITY = "humidity"
ATTR_NITROGEN_DIOXIDE = "nitrogen_dioxide"
ATTR_OZONE = "ozone"
ATTR_PM10 = "pm_10"
ATTR_PM2_5 = "pm_2_5"
ATTR_PRESSURE = "pressure"
ATTR_SULFUR_DIOXIDE = "sulfur_dioxide"

ATTRIBUTION = "Data provided by the World Air Quality Index project"

ATTR_ICON = "mdi:cloud"

CONF_LOCATIONS = "locations"
CONF_STATIONS = "stations"

TIMEOUT = 10

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_STATIONS): cv.ensure_list,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_LOCATIONS): cv.ensure_list,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the requested World Air Quality Index locations."""

    token = config[CONF_TOKEN]
    station_filter = config.get(CONF_STATIONS)
    locations = config[CONF_LOCATIONS]

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.02.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "World Air Quality Index",
        },
    )

    client = WAQIClient(session=async_get_clientsession(hass), request_timeout=TIMEOUT)
    client.authenticate(token)
    try:
        for location_name in locations:
            stations = await client.search(location_name)
            _LOGGER.debug("The following stations were returned: %s", stations)
            for station in stations:
                if not station_filter or {
                    station.station_id,
                    station.station.external_url,
                    station.station.name,
                } & set(station_filter):
                    hass.async_create_task(
                        hass.config_entries.flow.async_init(
                            DOMAIN,
                            context={"source": SOURCE_IMPORT},
                            data={
                                CONF_STATION_NUMBER: station.station_id,
                                CONF_NAME: station.station.name,
                                CONF_API_KEY: config[CONF_TOKEN],
                            },
                        )
                    )
    except WAQIAuthenticationError as err:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue_invalid_auth",
            breaks_in_ha_version="2024.02.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_invalid_auth",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )
        _LOGGER.exception("Could not authenticate with WAQI")
        raise PlatformNotReady from err
    except WAQIConnectionError as err:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue_cannot_connect",
            breaks_in_ha_version="2024.02.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_cannot_connect",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )
        _LOGGER.exception("Failed to connect to WAQI servers")
        raise PlatformNotReady from err


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WAQI sensor."""
    coordinator: WAQIDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WaqiSensor(coordinator)])


class WaqiSensor(CoordinatorEntity[WAQIDataUpdateCoordinator], SensorEntity):
    """Implementation of a WAQI sensor."""

    _attr_icon = ATTR_ICON
    _attr_device_class = SensorDeviceClass.AQI
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: WAQIDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = f"WAQI {self.coordinator.data.city.name}"
        self._attr_unique_id = str(coordinator.data.station_id)

    @property
    def native_value(self) -> int | None:
        """Return the state of the device."""
        return self.coordinator.data.air_quality_index

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the last update."""
        attrs = {}
        try:
            attrs[ATTR_ATTRIBUTION] = " and ".join(
                [ATTRIBUTION]
                + [
                    attribution.name
                    for attribution in self.coordinator.data.attributions
                ]
            )

            attrs[ATTR_TIME] = self.coordinator.data.measured_at
            attrs[ATTR_DOMINENTPOL] = self.coordinator.data.dominant_pollutant

            iaqi = self.coordinator.data.extended_air_quality

            attribute = {
                ATTR_PM2_5: iaqi.pm25,
                ATTR_PM10: iaqi.pm10,
                ATTR_HUMIDITY: iaqi.humidity,
                ATTR_PRESSURE: iaqi.pressure,
                ATTR_TEMPERATURE: iaqi.temperature,
                ATTR_OZONE: iaqi.ozone,
                ATTR_NITROGEN_DIOXIDE: iaqi.nitrogen_dioxide,
                ATTR_SULFUR_DIOXIDE: iaqi.sulfur_dioxide,
            }
            res_attributes = {k: v for k, v in attribute.items() if v is not None}
            return {**attrs, **res_attributes}
        except (IndexError, KeyError):
            return {ATTR_ATTRIBUTION: ATTRIBUTION}
