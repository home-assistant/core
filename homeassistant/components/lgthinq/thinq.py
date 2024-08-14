"""Support for LG ThinQ Connect API."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
from thinqconnect.thinq_api import ThinQApi, ThinQApiResponse

_LOGGER = logging.getLogger(__name__)


class ThinQ:
    """The class for using LG ThinQ Connect API."""

    def __init__(
        self,
        client_session: ClientSession,
        country_code: str,
        client_id: str,
        access_token: str,
    ) -> None:
        """Initialize settings."""
        self._client_id = client_id
        self._api = ThinQApi(
            session=client_session,
            access_token=access_token,
            country_code=country_code,
            client_id=client_id,
        )

    @property
    def api(self) -> ThinQApi:
        """Returns the api instance."""
        return self._api

    @property
    def client_id(self) -> str:
        """Returns the api instance."""
        return self._client_id

    @staticmethod
    def is_success(response: ThinQApiResponse) -> bool:
        """Check whether the response is success."""
        return 200 <= response.status < 300

    def _handle_response(self, response: ThinQApiResponse) -> dict[str, Any] | None:
        """Handle the response."""
        return response.body if ThinQ.is_success(response) else None

    async def async_get_device_list(self) -> ThinQApiResponse:
        """Get the list of devices."""
        _LOGGER.debug("async_get_device_list")

        # GET /devices
        return await self._api.async_get_device_list()

    async def async_get_device_profile(self, device_id: str) -> dict[str, Any] | None:
        """Get the device profile for the given device id."""
        _LOGGER.debug("async_get_device_profile: device_id=%s", device_id)

        # GET /devices/profile/{device-id}
        return self._handle_response(
            await self._api.async_get_device_profile(device_id)
        )

    async def async_get_device_status(self, device_id: str) -> ThinQApiResponse:
        """Get the device status for the given device id."""
        _LOGGER.debug("async_get_device_status: device_id=%s", device_id)

        # GET /devices/{device-id}
        return await self._api.async_get_device_status(device_id)

    async def async_post_device_status(
        self, device_id: str, body: Any
    ) -> ThinQApiResponse:
        """Post the device status for the given device id."""
        _LOGGER.debug(
            "async_post_device_status: device_id=%s, body=%s", device_id, body
        )

        # POST /devices/{device-id}
        return await self._api.async_post_device_control(device_id, body)

    async def async_post_client_register(
        self, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Post the client register request."""
        _LOGGER.debug("async_post_client_register")

        # POST /client
        return self._handle_response(await self._api.async_post_client_register(body))

    async def async_delete_client_register(
        self, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Delete the client register request."""
        _LOGGER.debug("async_delete_client_register")

        # Delete /client
        return self._handle_response(await self._api.async_delete_client_register(body))

    async def async_get_route(self) -> dict[str, Any] | None:
        """Get the route lists."""
        _LOGGER.debug("async_get_route")

        # Get /route
        return self._handle_response(await self._api.async_get_route())

    async def async_post_client_certificate(
        self, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Post the client certificate request."""
        _LOGGER.debug("async_post_client_certificate")

        # POST /client/certificate
        return self._handle_response(
            await self._api.async_post_client_certificate(body)
        )

    async def async_get_push_list(self) -> dict[str, Any] | None:
        """Get the push device lists."""
        _LOGGER.debug("async_get_push_list")

        # Get /push
        return self._handle_response(await self._api.async_get_push_list())

    async def async_post_push_subscribe(self, device_id: str) -> dict[str, Any] | None:
        """Subscribe the push for the given device id."""
        _LOGGER.debug("async_post_push_subscribe: device_id=%s", device_id)

        # POST /push/{device-id}/subscribe
        return self._handle_response(
            await self._api.async_post_push_subscribe(device_id)
        )

    async def async_delete_push_subscribe(
        self, device_id: str
    ) -> dict[str, Any] | None:
        """Unsubscribe the push for the given device id."""
        _LOGGER.debug("async_delete_push_subscribe: device_id=%s", device_id)

        # DELETE /push/{device_id}/unsubscribe
        return self._handle_response(
            await self._api.async_delete_push_subscribe(device_id)
        )

    async def async_get_event_list(self) -> dict[str, Any] | None:
        """Get the event device lists."""
        _LOGGER.debug("async_get_event_list")

        # Get /event
        return self._handle_response(await self._api.async_get_event_list())

    async def async_post_event_subscribe(
        self, device_id: str, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Subscribe the event for the given device id."""
        _LOGGER.debug("async_post_event_subscribe: device_id=%s", device_id)

        # POST /event/{device_id}/subscribe
        return self._handle_response(
            await self._api.async_post_event_subscribe(device_id)
        )

    async def async_delete_event_subscribe(
        self, device_id: str
    ) -> dict[str, Any] | None:
        """Unsubscribe the event for the given device id."""
        _LOGGER.debug("async_delete_event_subscribe: device_id=%s", device_id)

        # DELETE /event/{device_id}/unsubscribe
        return self._handle_response(
            await self._api.async_delete_event_subscribe(device_id)
        )

    async def async_post_push_devices_subscribe(self) -> dict[str, Any] | None:
        """Subscribe the push for device addition, deletion, and modification."""
        _LOGGER.debug("async_post_push_devices_subscribe")

        # POST /homes/push
        return self._handle_response(
            await self._api.async_post_push_devices_subscribe()
        )

    async def async_delete_push_devices_subscribe(
        self,
    ) -> dict[str, Any] | None:
        """Unsubscribe the push for device addition, deletion, and modification."""
        _LOGGER.debug("async_delete_push_devices_subscribe")

        # DELETE /homes/push
        return self._handle_response(
            await self._api.async_delete_push_devices_subscribe()
        )
