"""Library for interfacing with the SensorPush Cloud API."""

from __future__ import annotations

from asyncio import Lock
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from datetime import datetime
from functools import wraps
from typing import Any, Concatenate

from sensorpush_api import (
    AccessTokenRequest,
    ApiApi,
    ApiClient,
    AuthorizeRequest,
    Configuration,
    Samples,
    SamplesRequest,
    Sensor,
    SensorsRequest,
)

from homeassistant.util import dt as dt_util

from .const import ACCESS_TOKEN_EXPIRATION, LOGGER, REQUEST_RETRIES, REQUEST_TIMEOUT


def api_call[**_P, _R](
    func: Callable[Concatenate[SensorPushCloudApi, _P], Awaitable[_R]],
) -> Callable[Concatenate[SensorPushCloudApi, _P], Coroutine[Any, Any, _R]]:
    """Decorate API calls to handle SensorPush Cloud exceptions."""

    @wraps(func)
    async def _api_call(
        self: SensorPushCloudApi, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        retries: int = 0
        LOGGER.debug(f"API call to {func} with args={args}, kwargs={kwargs}")
        while True:
            try:
                result = await func(self, *args, **kwargs)
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
                raise SensorPushCloudError from e
            else:
                LOGGER.debug(f"API call to {func} succeeded after {retries} retries")
                return result

    return _api_call


class SensorPushCloudError(Exception):
    """An exception occurred when calling the SensorPush Cloud API."""


class SensorPushCloudApi:
    """SensorPush Cloud API class."""

    email: str
    password: str
    configuration: Configuration
    api: ApiApi
    deadline: datetime
    lock: Lock

    def __init__(self, email: str, password: str) -> None:
        """Initialize the SensorPush Cloud API object."""
        self.email = email
        self.password = password
        self.configuration = Configuration()
        self.api = ApiApi(ApiClient(self.configuration))
        self.deadline = dt_util.now()
        self.lock = Lock()

    async def async_renew_access(self) -> None:
        """Renew an access token if it has expired."""
        async with self.lock:  # serialize authorize calls
            if dt_util.now() >= self.deadline:
                await self.async_authorize()

    @api_call
    async def async_authorize(self) -> None:
        """Sign in and request an authorization code."""
        # SensorPush provides a simplified OAuth endpoint using access tokens
        # without refresh tokens. It is not possible to use 3rd party client
        # IDs without first contacting SensorPush support.
        auth_response = await self.api.oauth_authorize_post(
            AuthorizeRequest(email=self.email, password=self.password),
            _request_timeout=REQUEST_TIMEOUT.total_seconds(),
        )
        access_response = await self.api.access_token(
            AccessTokenRequest(authorization=auth_response.authorization),
            _request_timeout=REQUEST_TIMEOUT.total_seconds(),
        )
        self.configuration.api_key["oauth"] = access_response.accesstoken
        self.deadline = dt_util.now() + ACCESS_TOKEN_EXPIRATION

    @api_call
    async def async_sensors(self, *args: Any, **kwargs: Any) -> Mapping[str, Sensor]:
        """List all sensors."""
        await self.async_renew_access()
        return await self.api.sensors(
            SensorsRequest(*args, **kwargs),
            _request_timeout=REQUEST_TIMEOUT.total_seconds(),
        )

    @api_call
    async def async_samples(self, *args: Any, **kwargs: Any) -> Samples:
        """Query sensor samples."""
        await self.async_renew_access()
        return await self.api.samples(
            SamplesRequest(*args, **kwargs),
            _request_timeout=REQUEST_TIMEOUT.total_seconds(),
        )
