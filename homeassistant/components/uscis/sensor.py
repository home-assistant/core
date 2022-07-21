"""Support for USCIS Case Status."""
from __future__ import annotations

from datetime import timedelta
import logging
from lxml import html
import requests
import re
from datetime import datetime
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "USCIS"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required("case_id"): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the platform in Home Assistant and Case Information."""
    uscis = USCISSensor(config["case_id"], config[CONF_NAME])
    uscis.update()
    if uscis.valid_case_id:
        add_entities([uscis])
    else:
        _LOGGER.error("USCIS Sensor setup Failed. Check if your Case ID is Valid.")


class USCISSensor(SensorEntity):
    """USCIS Sensor will check case status on daily basis."""
    CASE_DATE_PATTERN = r"[(A-Za-z)]*\s[\d]*,\s[\d]*"
    MIN_TIME_BETWEEN_UPDATES = timedelta(hours=24)
    URL = "https://egov.uscis.gov/casestatus/mycasestatus.do"
    APP_RECEIPT_NUMBER = "appReceiptNum"
    STATUS_HEADER_XPATH = "/html/body/div[2]/form/div/div[1]/div/div/div[2]/div[3]/h1/text()"
    STATUS_TEXT_XPATH = "/html/body/div[2]/form/div/div[1]/div/div/div[2]/div[3]/p/text()"

    SHORT_STATUS = "short_status"
    CURRENT_STATUS = "current_status"
    LAST_CASE_UPDATE_DATE = "last_update_date"

    def __init__(self, case, name):
        """Initialize the sensor."""
        self._state = None
        self._case_id = case
        self._attributes = None
        self.valid_case_id = None
        self._name = name

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def native_value(self):
        """Return the state."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch data from the USCIS website and update state attributes."""
        response = requests.post(USCISSensor.URL, {USCISSensor.APP_RECEIPT_NUMBER: self._case_id})
        parsed_html = html.fromstring(response.content)
        status_text = parsed_html.xpath(USCISSensor.STATUS_TEXT_XPATH)[0]
        if len(status_text) < 2:
            _LOGGER('Invalid status. Please check your USCIS case id.')
            self.valid_case_id = False
            return
        short_status = parsed_html.xpath(USCISSensor.STATUS_HEADER_XPATH)[0]
        match = re.search(USCISSensor.CASE_DATE_PATTERN, status_text)
        last_case_update_date = 'Invalid'
        if match is not None:
            last_case_update_date = datetime.strptime(str(match.group(0)), "%B %d, %Y")
            last_case_update_date = last_case_update_date.strftime("%m/%d/%Y")
        self._attributes = {USCISSensor.CURRENT_STATUS: status_text, USCISSensor.LAST_CASE_UPDATE_DATE: last_case_update_date}
        self._state = short_status
        self.valid_case_id = True
