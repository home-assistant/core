"""
Support for USCIS Case Status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.uscis/
"""

import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_FRIENDLY_NAME


_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['lxml==3.5.0']

DEFAULT_NAME = "USCIS"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FRIENDLY_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required('case_id'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setting the platform in HASS and Case Information."""
    uscis = UscisSensor(config['case_id'], config[CONF_FRIENDLY_NAME])
    uscis.update()
    if uscis.valid_case_id:
        add_devices([uscis])
    else:
        _LOGGER.error("Setup USCIS Sensor Fail"
                      " check if your Case ID is Valid")
    return


class UscisSensor(Entity):
    """USCIS Sensor will check case status on daily basis."""

    HOURS_TO_UPDATE = timedelta(hours=24)

    CURRENT_STATUS = "current_status"
    LAST_CASE_UPDATE = "last_update_date"
    CASE_DATE_PATTERN = r"[(A-Za-z)]*\s[\d]*,\s[\d]*"
    URL = "https://egov.uscis.gov/casestatus/mycasestatus.do"
    APP_RECEIPT_NUM = "appReceiptNum"
    INIT_CASE_SEARCH = "initCaseSearch"
    CASE_STATUS = "CHECK STATUS"
    UPDATE_TEXT_XPATH = "/html/body/div[2]/form/div/div[1]" \
                        "/div/div/div[2]/div[3]/p/text()"
    USCIS_WEBSITE = "http://egov.uscis.gov/"
    MISSING_URL_PATTEN = "','|', '"
    TEXT_FILTER_PATTERN = r"['\[\]]"

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
    def state(self):
        """Return the state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @Throttle(HOURS_TO_UPDATE)
    def update(self):
        """Using Request to access USCIS website and fetch data."""
        import requests
        import re
        from datetime import datetime
        from lxml import html

        data = {self.APP_RECEIPT_NUM: self._case_id,
                self.INIT_CASE_SEARCH: self.CASE_STATUS}
        request = requests.post(self.URL, data=data)

        content = html.fromstring(request.content)
        text = str(content.xpath(self.UPDATE_TEXT_XPATH))
        if len(text) > 2:
            text = str(re.sub("','|', '", 'USCIS website', text))
            status_message = re.sub(r"['\[\]]", ' ', text)
            p_search = re.search(self.CASE_DATE_PATTERN, status_message)
            match = p_search.group(0)

            last_update_date = datetime.strptime(str(match), "%B %d, %Y")
            last_update_date = last_update_date.strftime('%m/%d/%Y')

            self._attributes = {
                self.CURRENT_STATUS: status_message,
                self.LAST_CASE_UPDATE: last_update_date
            }
            self._state = last_update_date
            self.valid_case_id = True

        else:
            self.valid_case_id = False
            _LOGGER.error("Invalid Case Id for USCIS")
