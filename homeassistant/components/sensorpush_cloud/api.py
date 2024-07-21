"""Library for interfacing with the SensorPush Cloud API."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from functools import partial, wraps
import json
from threading import Lock
from typing import Any, Concatenate

from sensorpush_api import (
    AccessTokenRequest,
    ApiApi,
    ApiClient,
    AuthorizeRequest,
    Configuration,
    Samples,
    SamplesRequest,
    Sensors,
    SensorsRequest,
)
from sensorpush_api.rest import ApiException

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import ACCESS_TOKEN_EXPIRATION, LOGGER, REQUEST_RETRIES, REQUEST_TIMEOUT


def api_call[**_P, _R](
    func: Callable[Concatenate[SensorPushCloudApi, _P], _R],
) -> Callable[Concatenate[SensorPushCloudApi, _P], _R]:
    """Decorate API calls to handle SensorPush Cloud exceptions."""

    @wraps(func)
    def _api_call(self: SensorPushCloudApi, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        LOGGER.debug(f"API call to {func} with args={args}, kwargs={kwargs}")
        retries: int = 0
        while True:
            try:
                result = func(self, *args, **kwargs)
            except Exception as e:
                # Force reauthorization if an exception occurs to avoid
                # authorization failures after temporary outages.
                self.deadline = dt_util.now()

                # The SensorPush Cloud API suffers from frequent exceptions;
                # requests are retried before raising an error.
                if retries < REQUEST_RETRIES:
                    retries = retries + 1
                    continue

                LOGGER.debug(f"API call to {func} failed after {retries} retries")
                if isinstance(e, ApiException):
                    # API exceptions provide a JSON-encoded message in the
                    # body; otherwise, fall back to the general behavior.
                    try:
                        data = json.loads(e.body)
                        raise SensorPushCloudError(data["message"]) from e
                    except Exception:  # noqa: BLE001
                        pass
                raise SensorPushCloudError from e
            else:
                LOGGER.debug(f"API call to {func} succeeded after {retries} retries")
                return result

    return _api_call


class SensorPushCloudError(Exception):
    """An exception occurred when calling the SensorPush Cloud API."""


class SensorPushCloudApi:
    """SensorPush Cloud API class."""

    hass: HomeAssistant
    email: str
    password: str
    configuration: Configuration
    api: ApiApi
    deadline: datetime
    lock: Lock

    def __init__(self, hass: HomeAssistant, email: str, password: str) -> None:
        """Initialize the SensorPush Cloud API object."""
        self.hass = hass
        self.email = email
        self.password = password
        # Generated Swagger clients install default logging handlers that
        # conflict with Home Assistant; remove before making API calls.
        self.configuration = Configuration()
        for logger in self.configuration.logger.values():
            logger.removeHandler(self.configuration.logger_stream_handler)
        self.api = ApiApi(ApiClient(self.configuration))
        self.deadline = dt_util.now()
        self.lock = Lock()

    @api_call
    def authorize(self) -> None:
        """Sign in and request an authorization code."""
        # SensorPush provides a simplified OAuth endpoint using access tokens
        # without refresh tokens. It is not possible to use 3rd party client
        # IDs without first contacting SensorPush support.
        response = self.api.oauth_authorize_post(
            AuthorizeRequest(email=self.email, password=self.password),
            _request_timeout=REQUEST_TIMEOUT.total_seconds(),
        )
        response = self.api.access_token(
            AccessTokenRequest(authorization=response.authorization),
            _request_timeout=REQUEST_TIMEOUT.total_seconds(),
        )
        self.configuration.api_key["Authorization"] = response.accesstoken
        self.deadline = dt_util.now() + ACCESS_TOKEN_EXPIRATION

    async def async_authorize(self) -> None:
        """Sign in and request an authorization code."""
        return await self.hass.async_add_executor_job(self.authorize)

    def renew_access_token(self) -> None:
        """Renew an access token if it has expired."""
        with self.lock:  # serialize authorize calls
            if dt_util.now() >= self.deadline:
                self.authorize()

    @api_call
    def sensors(self, *args: Any, **kwargs: Any) -> Sensors:
        """List all sensors."""
        self.renew_access_token()
        return self.api.sensors(
            SensorsRequest(*args, **kwargs),
            _request_timeout=REQUEST_TIMEOUT.total_seconds(),
        )

    async def async_sensors(self, *args: Any, **kwargs: Any) -> Sensors:
        """List all sensors."""
        return await self.hass.async_add_executor_job(
            partial(self.sensors, *args, **kwargs)
        )

    @api_call
    def samples(self, *args: Any, **kwargs: Any) -> Samples:
        """Query sensor samples."""
        self.renew_access_token()
        return self.api.samples(
            SamplesRequest(*args, **kwargs),
            _request_timeout=REQUEST_TIMEOUT.total_seconds(),
        )

    async def async_samples(self, *args: Any, **kwargs: Any) -> Samples:
        """Query sensor samples."""
        return await self.hass.async_add_executor_job(
            partial(self.samples, *args, **kwargs)
        )
