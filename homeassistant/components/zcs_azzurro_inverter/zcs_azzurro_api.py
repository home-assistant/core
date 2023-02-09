"""ZCS Azzurro API."""
import logging
from typing import Any

import requests
from requests.exceptions import HTTPError

_LOGGER = logging.getLogger(__name__)


class ZcsAzzurroApi:
    """Class implementing ZCS Azzurro API for inverters."""

    ENDPOINT = "https://third.zcsazzurroportal.com:19003"
    AUTH_KEY = "Authorization"
    AUTH_VALUE = "Zcs eHWAeEq0aYO0"
    CLIENT_AUTH_KEY = "client"
    CONTENT_TYPE = "application/json"
    REQUEST_TIMEOUT = 5

    HISTORIC_DATA_KEY = "historicData"
    HISTORIC_DATA_COMMAND = "historicData"

    REALTIME_DATA_KEY = "realtimeData"
    REALTIME_DATA_COMMAND = "realtimeData"

    DEVICES_ALARMS_KEY = "deviceAlarm"
    DEVICES_ALARMS_COMMAND = "deviceAlarm"

    COMMAND_KEY = "command"
    PARAMS_KEY = "params"
    PARAMS_THING_KEY = "thingKey"
    PARAMS_REQUIRED_VALUES_KEY = "requiredValues"
    PARAMS_START_KEY = "start"
    PARAMS_END_KEY = "end"

    RESPONSE_SUCCESS_KEY = "success"
    RESPONSE_VALUES_KEY = "value"

    # Values of required values
    REQUIRED_VALUES_ALL = "*"
    REQUIRED_VALUES_SEP = ","

    def __init__(self, client: str, thing_serial: str, name: str | None = None) -> None:
        """Class initialization."""
        self.client = client
        self._thing_serial = thing_serial
        self.name = name or self._thing_serial

    def _post_request(self, data: dict) -> requests.Response:
        """client: the client to set in header.

        data: the dictionary to be sent as json
        return: the response from request.
        """
        headers = {
            ZcsAzzurroApi.AUTH_KEY: ZcsAzzurroApi.AUTH_VALUE,
            ZcsAzzurroApi.CLIENT_AUTH_KEY: self.client,
            "Content-Type": ZcsAzzurroApi.CONTENT_TYPE,
        }

        _LOGGER.debug(
            "post_request called with client %s, data %s. headers are %s",
            self.client,
            data,
            headers,
        )
        response = requests.post(
            ZcsAzzurroApi.ENDPOINT,
            headers=headers,
            json=data,
            timeout=ZcsAzzurroApi.REQUEST_TIMEOUT,
        )
        if response.status_code == 401:
            raise HTTPError(f"{response.status_code}: Authentication Error")
        return response

    def realtime_data_request(
        self,
        required_values: list[str] | None = None,
    ) -> dict:
        """Request realtime data."""
        if not required_values:
            required_values = [ZcsAzzurroApi.REQUIRED_VALUES_ALL]
        data = {
            ZcsAzzurroApi.REALTIME_DATA_KEY: {
                ZcsAzzurroApi.COMMAND_KEY: ZcsAzzurroApi.REALTIME_DATA_COMMAND,
                ZcsAzzurroApi.PARAMS_KEY: {
                    ZcsAzzurroApi.PARAMS_THING_KEY: self._thing_serial,
                    ZcsAzzurroApi.PARAMS_REQUIRED_VALUES_KEY: ZcsAzzurroApi.REQUIRED_VALUES_SEP.join(
                        required_values
                    ),
                },
            }
        }
        response = self._post_request(data)
        if not response.ok:
            raise ConnectionError("Response did not return correctly")
        response_data: dict[str, Any] = response.json()[ZcsAzzurroApi.REALTIME_DATA_KEY]
        _LOGGER.debug("fetched realtime data %s", response_data)
        if not response_data[ZcsAzzurroApi.RESPONSE_SUCCESS_KEY]:
            raise ConnectionError("Response did not return correctly")
        return response_data[ZcsAzzurroApi.PARAMS_KEY][
            ZcsAzzurroApi.RESPONSE_VALUES_KEY
        ][0][self._thing_serial]

    def alarms_request(self) -> dict:
        """Request alarms."""
        required_values = [ZcsAzzurroApi.REQUIRED_VALUES_ALL]
        data = {
            ZcsAzzurroApi.DEVICES_ALARMS_KEY: {
                ZcsAzzurroApi.COMMAND_KEY: ZcsAzzurroApi.DEVICES_ALARMS_COMMAND,
                ZcsAzzurroApi.PARAMS_KEY: {
                    ZcsAzzurroApi.PARAMS_THING_KEY: self._thing_serial,
                    ZcsAzzurroApi.PARAMS_REQUIRED_VALUES_KEY: ZcsAzzurroApi.REQUIRED_VALUES_SEP.join(
                        required_values
                    ),
                },
            }
        }
        response = self._post_request(data)
        if not response.ok:
            raise ConnectionError("Response did not return correctly")
        response_data: dict[str, Any] = response.json()[
            ZcsAzzurroApi.DEVICES_ALARMS_KEY
        ]
        _LOGGER.debug("fetched realtime data %s", response_data)
        if not response_data[ZcsAzzurroApi.RESPONSE_SUCCESS_KEY]:
            raise ConnectionError("Response did not return correctly")
        return response_data[ZcsAzzurroApi.PARAMS_KEY][
            ZcsAzzurroApi.RESPONSE_VALUES_KEY
        ][0][self._thing_serial]

    @property
    def identifier(self):
        """object identifier."""
        return f"{self.client}_{self._thing_serial}"
