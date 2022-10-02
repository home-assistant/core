"""Support for getting data from websites with scraping."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from bs4 import BeautifulSoup
import httpx
import voluptuous as vol

from homeassistant.components.rest.data import RestData
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    STATE_CLASSES_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=10)

CONF_ATTR = "attribute"
CONF_SELECT = "select"
CONF_INDEX = "index"

DEFAULT_NAME = "Web scrape"
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.string,
        vol.Required(CONF_SELECT): cv.string,
        vol.Optional(CONF_ATTR): cv.string,
        vol.Optional(CONF_INDEX, default=0): cv.positive_int,
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Web scrape sensor."""
    name: str = config[CONF_NAME]
    resource: str = config[CONF_RESOURCE]
    method: str = "GET"
    payload: str | None = None
    headers: str | None = config.get(CONF_HEADERS)
    verify_ssl: bool = config[CONF_VERIFY_SSL]
    select: str | None = config.get(CONF_SELECT)
    attr: str | None = config.get(CONF_ATTR)
    index: int = config[CONF_INDEX]
    unit: str | None = config.get(CONF_UNIT_OF_MEASUREMENT)
    device_class: str | None = config.get(CONF_DEVICE_CLASS)
    state_class: str | None = config.get(CONF_STATE_CLASS)
    username: str | None = config.get(CONF_USERNAME)
    password: str | None = config.get(CONF_PASSWORD)
    value_template: Template | None = config.get(CONF_VALUE_TEMPLATE)

    if value_template is not None:
        value_template.hass = hass

    auth: httpx.DigestAuth | tuple[str, str] | None = None
    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = httpx.DigestAuth(username, password)
        else:
            auth = (username, password)

    rest = RestData(hass, method, resource, auth, headers, None, payload, verify_ssl)
    await rest.async_update()

    if rest.data is None:
        raise PlatformNotReady

    async_add_entities(
        [
            ScrapeSensor(
                rest,
                name,
                select,
                attr,
                index,
                value_template,
                unit,
                device_class,
                state_class,
            )
        ],
        True,
    )


class ScrapeSensor(SensorEntity):
    """Representation of a web scrape sensor."""

    def __init__(
        self,
        rest: RestData,
        name: str,
        select: str | None,
        attr: str | None,
        index: int,
        value_template: Template | None,
        unit: str | None,
        device_class: str | None,
        state_class: str | None,
    ) -> None:
        """Initialize a web scrape sensor."""
        self.rest = rest
        self._attr_native_value = None
        self._select = select
        self._attr = attr
        self._index = index
        self._value_template = value_template
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    def _extract_value(self) -> Any:
        """Parse the html extraction in the executor."""
        raw_data = BeautifulSoup(self.rest.data, "lxml")
        _LOGGER.debug(raw_data)

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
            _LOGGER.warning("Index '%s' not found in %s", self._attr, self.entity_id)
            value = None
        except KeyError:
            _LOGGER.warning(
                "Attribute '%s' not found in %s", self._attr, self.entity_id
            )
            value = None
        _LOGGER.debug(value)
        return value

    async def async_update(self) -> None:
        """Get the latest data from the source and updates the state."""
        await self.rest.async_update()
        await self._async_update_from_rest_data()

    async def async_added_to_hass(self) -> None:
        """Ensure the data from the initial update is reflected in the state."""
        await self._async_update_from_rest_data()

    async def _async_update_from_rest_data(self) -> None:
        """Update state from the rest data."""
        if self.rest.data is None:
            _LOGGER.error("Unable to retrieve data for %s", self.name)
            return

        value = await self.hass.async_add_executor_job(self._extract_value)

        if self._value_template is not None:
            self._attr_native_value = (
                self._value_template.async_render_with_possible_json_value(value, None)
            )
        else:
            self._attr_native_value = value
