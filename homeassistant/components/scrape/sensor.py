"""Support for getting data from websites with scraping."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.rest import RESOURCE_SCHEMA, create_rest_data_from_config
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    STATE_CLASSES_SCHEMA,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.template import Template
from homeassistant.helpers.template_entity import (
    TEMPLATE_SENSOR_BASE_SCHEMA,
    TemplateSensor,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import ScrapeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        # Linked to the loading of the page (can be linked to RestData)
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Required(CONF_RESOURCE): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        # Linked to the parsing of the page (specific to scrape)
        vol.Optional(CONF_ATTRIBUTE): cv.string,
        vol.Optional(CONF_INDEX, default=0): cv.positive_int,
        vol.Required(CONF_SELECT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        # Linked to the sensor definition (can be linked to TemplateSensor)
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Web scrape sensor."""
    coordinator: ScrapeCoordinator
    sensors_config: list[ConfigType]
    if discovery_info is None:
        async_create_issue(
            hass,
            DOMAIN,
            "moved_yaml",
            breaks_in_ha_version="2022.12.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="moved_yaml",
        )
        resource_config = vol.Schema(RESOURCE_SCHEMA, extra=vol.REMOVE_EXTRA)(config)
        rest = create_rest_data_from_config(hass, resource_config)

        scan_interval: timedelta = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        coordinator = ScrapeCoordinator(hass, rest, scan_interval)

        sensors_config = [
            vol.Schema(TEMPLATE_SENSOR_BASE_SCHEMA.schema, extra=vol.ALLOW_EXTRA)(
                config
            )
        ]

    else:
        coordinator = discovery_info["coordinator"]
        sensors_config = discovery_info["configs"]

    await coordinator.async_refresh()
    if coordinator.data is None:
        raise PlatformNotReady

    entities: list[ScrapeSensor] = []
    for sensor_config in sensors_config:
        value_template: Template | None = sensor_config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = hass

        entities.append(
            ScrapeSensor(
                hass,
                coordinator,
                sensor_config,
                sensor_config[CONF_NAME],
                sensor_config.get(CONF_UNIQUE_ID),
                sensor_config[CONF_SELECT],
                sensor_config.get(CONF_ATTRIBUTE),
                sensor_config[CONF_INDEX],
                value_template,
            )
        )

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Scrape sensor entry."""
    entities: list = []

    coordinator: ScrapeCoordinator = hass.data[DOMAIN][entry.entry_id]
    config = dict(entry.options)
    for sensor in config["sensor"]:
        sensor_config: ConfigType = vol.Schema(
            TEMPLATE_SENSOR_BASE_SCHEMA.schema, extra=vol.ALLOW_EXTRA
        )(sensor)

        name: str = sensor_config[CONF_NAME]
        select: str = sensor_config[CONF_SELECT]
        attr: str | None = sensor_config.get(CONF_ATTRIBUTE)
        index: int = int(sensor_config[CONF_INDEX])
        value_string: str | None = sensor_config.get(CONF_VALUE_TEMPLATE)
        unique_id: str = sensor_config[CONF_UNIQUE_ID]

        value_template: Template | None = (
            Template(value_string, hass) if value_string is not None else None
        )
        entities.append(
            ScrapeSensor(
                hass,
                coordinator,
                sensor_config,
                name,
                unique_id,
                select,
                attr,
                index,
                value_template,
            )
        )

    async_add_entities(entities)


class ScrapeSensor(CoordinatorEntity[ScrapeCoordinator], TemplateSensor):
    """Representation of a web scrape sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        config: ConfigType,
        name: str,
        unique_id: str | None,
        select: str,
        attr: str | None,
        index: int,
        value_template: Template | None,
    ) -> None:
        """Initialize a web scrape sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        TemplateSensor.__init__(
            self,
            hass,
            config=config,
            fallback_name=name,
            unique_id=unique_id,
        )
        self._select = select
        self._attr = attr
        self._index = index
        self._value_template = value_template

    def _extract_value(self) -> Any:
        """Parse the html extraction in the executor."""
        raw_data = self.coordinator.data
        try:
            if self._attr is not None:
                value = raw_data.select(self._select)[self._index][self._attr]
            else:
                tag = raw_data.select(self._select)[self._index]
                if tag.name in ("style", "script", "template"):
                    value = tag.string
                else:
                    value = tag.text
        except IndexError:
            _LOGGER.warning("Index '%s' not found in %s", self._index, self.entity_id)
            value = None
        except KeyError:
            _LOGGER.warning(
                "Attribute '%s' not found in %s", self._attr, self.entity_id
            )
            value = None
        _LOGGER.debug("Parsed value: %s", value)
        return value

    async def async_added_to_hass(self) -> None:
        """Ensure the data from the initial update is reflected in the state."""
        await super().async_added_to_hass()
        self._async_update_from_rest_data()

    def _async_update_from_rest_data(self) -> None:
        """Update state from the rest data."""
        value = self._extract_value()

        if self._value_template is not None:
            self._attr_native_value = (
                self._value_template.async_render_with_possible_json_value(value, None)
            )
        else:
            self._attr_native_value = value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_from_rest_data()
        super()._handle_coordinator_update()
