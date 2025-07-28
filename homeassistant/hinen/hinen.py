"""Hinen Open API client."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from logging import getLogger
from typing import Any, TypeVar

from aiohttp import ClientError, ClientResponse, ClientSession
from yarl import URL

from .hinen_exception import (
    ForbiddenError,
    HinenAPIError,
    HinenBackendError,
    HinenResourceNotFoundError,
    UnauthorizedError,
)
from .models import HinenDeviceDetail, HinenDeviceInfo

T = TypeVar("T")


class HinenOpen:
    """HinenOpen API client."""

    _close_session: bool = False

    logger = getLogger(__name__)

    _user_auth_token: str | None = None
    _user_auth_refresh_token: str | None = None
    _has_user_auth = False

    def __init__(
        self,
        host: str | None = None,
        app_id: str | None = None,
        app_secret: str | None = None,
        session: ClientSession | None = None,
        session_timeout: int = 10,
        auto_refresh_auth: bool | None = None,
    ) -> None:
        """Initialize Hinen Open object."""
        self.host = host
        self.app_id = app_id
        self.app_secret = app_secret
        self.session = session
        self.session_timeout = session_timeout

        if auto_refresh_auth is None:
            self.auto_refresh_auth = app_id is not None and app_secret is not None
        else:
            self.auto_refresh_auth = auto_refresh_auth

        self._r_lookup: dict[
            str,
            Callable[
                [ClientSession, str, dict[str, Any] | None],
                Coroutine[Any, Any, ClientResponse],
            ],
        ] = {
            "get": self._api_get_request,
        }

    async def _api_get_request(
        self,
        session: ClientSession,
        url: str,
        data: dict[str, Any] | None = None,
    ) -> ClientResponse:
        """Make GET request with authorization."""
        headers = {"Authorization": f"{self._user_auth_token}"}
        self.logger.debug("making GET request to %s", url)
        response = await session.get(url, headers=headers, json=data)
        return await self._check_request_return(response)

    async def _check_request_return(self, response: ClientResponse) -> ClientResponse:
        if response.status == 500:
            msg = "Internal Server Error"
            raise SystemExit(msg)
        if response.status == 400:
            msg = (await response.json()).get("message")
            raise SystemExit(
                "Bad Request" + ("" if msg is None else f" - {msg!s}"),
            )
        if response.status == 404:
            raise HinenResourceNotFoundError
        if response.status == 401:
            raise UnauthorizedError
        if response.status == 403:
            response_json = await response.json()
            error_message = response_json["error"]["errors"][0]["message"]
            raise ForbiddenError(error_message)
        if 400 <= response.status < 500:
            try:
                response.raise_for_status()
            except ClientError as exc:
                raise HinenAPIError from exc
        if (await response.json()).get("code") != "00000":
            raise HinenBackendError((await response.json()).get("data").get("message"))

        return response

    async def set_user_authentication(
        self,
        token: str,
        refresh_token: str | None = None,
    ) -> None:
        """Set a user token to be used.

        :param token: the generated user token
        :param refresh_token: The generated refresh token, has to be provided if
        :attr:`auto_refresh_auth` is True |default| :code:`None`
        """
        if refresh_token is None and self.auto_refresh_auth:
            msg = "refresh_token has to be provided when auto_refresh_auth is True"
            raise ValueError(msg)

        self._user_auth_token = token
        self._user_auth_refresh_token = refresh_token
        self._has_user_auth = True

    async def _build_generator(
        self,
        req: str,
        url: str,
        url_params: dict[str, Any],
        return_type: T,
        body_data: dict[str, Any] | None = None,
    ) -> AsyncGenerator[T]:
        method = self._r_lookup.get(req.lower(), self._api_get_request)
        if not self.session:
            self.session = ClientSession()
            self._close_session = True
        try:
            _url = f"{self.host}{url}"
            if url_params:
                _url = await self.build_url(_url, url_params)

            self.logger.info("making %s request to %s", req, _url)
            async with asyncio.timeout(self.session_timeout):
                response = await method(self.session, _url, body_data)

            if response.content_type != "application/json":
                msg = "Unexpected response type"
                raise HinenAPIError(msg)
            resp_data = (await response.json()).get("data")

            if not isinstance(resp_data, list):
                resp_data = [resp_data]

            for entry in resp_data:
                yield return_type(**entry)  # type: ignore[operator]
        except TimeoutError as exc:
            msg = "Timeout occurred"
            raise HinenBackendError(msg) from exc

    async def build_url(self, url: str, params: dict[str, Any], **kwargs: Any) -> str:
        """Build url from host and path."""
        return str(URL(url).with_query(**params).update_query(**kwargs))

    async def get_device_infos(self) -> AsyncGenerator[HinenDeviceInfo]:
        """Get device infos."""
        async for item in self._build_generator(
            "GET",
            "/iot-device/open-api/devices",
            {},
            HinenDeviceInfo,
        ):
            yield item  # type: ignore[misc]

    async def get_device_details(
        self,
        device_ids: list[str],
    ) -> AsyncGenerator[HinenDeviceDetail]:
        """Get device infos."""
        async for item in self._build_generator(
            "GET",
            f"/iot-device/open-api/devices/info/{device_ids[0]}",
            {},
            HinenDeviceDetail,
        ):
            yield item  # type: ignore[misc]

    async def close(self) -> None:
        """Close open client session."""
        if self.session and self._close_session:
            await self.session.close()

    async def __aenter__(self) -> "HinenOpen":
        """Async enter.

        Returns:
        ----
            The Hinen Open object.
        """
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Async exit.

        Args:
        ----
            _exc_info: Exec type.
        """
        await self.close()
