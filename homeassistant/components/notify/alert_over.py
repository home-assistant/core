import requests
import logging

import voluptuous as vol

from homeassistant.components.notify import (ATTR_TARGET, ATTR_TITLE, PLATFORM_SCHEMA, BaseNotificationService)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
CONF_FROM_SOURCE = "from_source"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FROM_SOURCE): cv.string,
})



def get_service(hass, config, discovery_info=None):
    return AlertOverNotificationService(config[CONF_FROM_SOURCE])


class AlertOverNotificationService(BaseNotificationService):
    def __init__(self, from_source):
        self.from_source = from_source

    def send_message(self, message="", **kwargs):
        receivers = kwargs.get(ATTR_TARGET)
        title = kwargs.get(ATTR_TITLE)
        try:
            for receiver in receivers:
                _LOGGER.info("已发送")

                data = {
                    "source": self.from_source,
                    "receiver": receiver,
                    "content": message,
                    "title": title
                }
                _LOGGER.info(data)
                requests.post(
                    "https://api.alertover.com/v1/alert",
                    data=data
                )

        except ConnectionError:
            _LOGGER.error("连接失败")
