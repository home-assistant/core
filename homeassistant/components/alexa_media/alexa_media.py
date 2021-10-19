"""
Alexa Devices Base Class.

SPDX-License-Identifier: Apache-2.0

For more details about this platform, please refer to the documentation at
https://community.home-assistant.io/t/echo-devices-alexa-as-media-player-testers-needed/58639
"""

import logging
from typing import Dict, Text  # noqa pylint: disable=unused-import

from alexapy import AlexaAPI, hide_email

from .const import DATA_ALEXAMEDIA

_LOGGER = logging.getLogger(__name__)


class AlexaMedia:
    """Implementation of Alexa Media Base object."""

    def __init__(self, device, login) -> None:
        # pylint: disable=unexpected-keyword-arg
        """Initialize the Alexa device."""

        # Class info
        self._login = login
        self.alexa_api = AlexaAPI(device, login)
        self.email = login.email
        self.account = hide_email(login.email)

    def check_login_changes(self):
        """Update Login object if it has changed."""
        # _LOGGER.debug("Checking if Login object has changed")
        try:
            login = self.hass.data[DATA_ALEXAMEDIA]["accounts"][self.email]["login_obj"]
        except (AttributeError, KeyError):
            return
        # _LOGGER.debug("Login object %s closed status: %s", login, login.session.closed)
        # _LOGGER.debug(
        #     "Alexaapi %s closed status: %s",
        #     self.alexa_api,
        #     self.alexa_api._session.closed,
        # )
        if self.alexa_api.update_login(login):
            _LOGGER.debug("Login object has changed; updating")
            self._login = login
            self.email = login.email
            self.account = hide_email(login.email)
