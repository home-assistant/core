"""Support for getting data from websites with scraping."""
import logging

from bs4 import BeautifulSoup
import httpx
import voluptuous as vol

from homeassistant.components.rest.data import RestData
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
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
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ATTR = "attribute"
CONF_SELECT = "select"
CONF_INDEX = "index"

DEFAULT_NAME = "Web scrape"
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Web scrape sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    method = "GET"
    payload = None
    headers = config.get(CONF_HEADERS)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    select = config.get(CONF_SELECT)
    attr = config.get(CONF_ATTR)
    index = config.get(CONF_INDEX)
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    device_class = config.get(CONF_DEVICE_CLASS)
    state_class = config.get(CONF_STATE_CLASS)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if (value_template := config.get(CONF_VALUE_TEMPLATE)) is not None:
        value_template.hass = hass

    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = httpx.DigestAuth(username, password)
        else:
            auth = (username, password)
    else:
        auth = None
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
        rest,
        name,
        select,
        attr,
        index,
        value_template,
        unit,
        device_class,
        state_class,
    ):
        """Initialize a web scrape sensor."""
        self.rest = rest
        self._state = None
        self._select = select
        self._attr = attr
        self._index = index
        self._value_template = value_template
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    def _extract_value(self):
        """Parse the html extraction in the executor."""
        raw_data = BeautifulSoup(self.rest.data, "html.parser")
        _LOGGER.debug(raw_data)

        if self._attr is not None:
            value = raw_data.select(self._select)[self._index][self._attr]
        else:
            tag = raw_data.select(self._select)[self._index]
            if tag.name in ("style", "script", "template"):
                value = tag.string
            else:
                value = tag.text
        _LOGGER.debug(value)
        return value

    async def async_update(self):
        """Get the latest data from the source and updates the state."""
        await self.rest.async_update()
        await self._async_update_from_rest_data()

    async def async_added_to_hass(self):
        """Ensure the data from the initial update is reflected in the state."""
        await self._async_update_from_rest_data()

    async def _async_update_from_rest_data(self):
        """Update state from the rest data."""
        if self.rest.data is None:
            _LOGGER.error("Unable to retrieve data for %s", self.name)
            return

        try:
            value = await self.hass.async_add_executor_job(self._extract_value)
        except IndexError:
            _LOGGER.error("Unable to extract data from HTML for %s", self.name)
            return

        if self._value_template is not None:
            self._state = self._value_template.async_render_with_possible_json_value(
                value, None
            )
        else:
            self._state = value
