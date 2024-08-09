# SPDX-FileCopyrightText: Copyright 2024 LG Electronics Inc.
# SPDX-License-Identifier: LicenseRef-LGE-Proprietary

"""Support for LG ThinQ Connect API."""

from __future__ import annotations

import logging
from collections.abc import Coroutine
from typing import Any

from aiohttp import ClientSession
from thinqconnect.thinq_api import ThinQApi, ThinQApiResponse

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ThinQ:
    """The class for using LG ThinQ Connect API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_session: ClientSession,
        country_code: str,
        client_id: str,
        access_token: str,
    ):
        """Initialize settings."""
        self._hass = hass
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

    async def _async_request(
        self,
        target: Coroutine[Any, Any, ThinQApiResponse],
        full_response: bool = False,
    ) -> Any:
        """Request common api and error handling."""
        result: ThinQApiResponse = await target
        return result if full_response else result.body

    async def async_get_device_list(self) -> list[dict] | None:
        """Get the list of devices."""
        _LOGGER.warning("async_get_device_list.")

        # GET /devices
        result: ThinQApiResponse = await self._async_request(
            self._api.async_get_device_list(),
            full_response=True,
        )
        if result.status >= 200 and result.status < 300:
            return result.body

        raise ConfigEntryError(
            result.error_message,
            translation_domain=DOMAIN,
            translation_key=result.error_code,
        )

    async def async_get_device_profile(
        self, device_id: str
    ) -> dict[str, Any] | None:
        """Get the device profile for the given device id."""
        _LOGGER.debug("async_get_device_profile. device_id=%s", device_id)

        # GET /devices/profile/{device-id}
        return await self._async_request(
            self._api.async_get_device_profile(device_id=device_id)
        )

    async def async_get_device_status(
        self, device_id: str
    ) -> ThinQApiResponse:
        """Get the device status for the given device id."""
        _LOGGER.debug("async_get_device_status. device_id=%s", device_id)

        # GET /devices/{device-id}
        return await self._async_request(
            self._api.async_get_device_status(device_id=device_id),
            full_response=True,
        )

    async def async_post_device_status(
        self, device_id: str, body: dict[str, Any]
    ) -> ThinQApiResponse:
        """Post the device status for the given device id."""
        _LOGGER.warning(
            "async_post_device_status. device_id=%s, body=%s", device_id, body
        )

        # POST /devices/{device-id}
        return await self._async_request(
            self._api.async_post_device_control(
                device_id=device_id, payload=body
            ),
            full_response=True,
        )

    async def async_post_client_register(
        self, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Post the client register request."""
        _LOGGER.warning("async_post_client_register")

        # POST /client
        return await self._async_request(
            self._api.async_post_client_register(json=body)
        )

    async def async_delete_client_register(
        self, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Delete the client register request."""
        _LOGGER.warning("async_delete_client_register")

        # Delete /client
        return await self._async_request(
            self._api.async_delete_client_register(json=body)
        )

    async def async_get_route(self) -> dict[str, Any] | None:
        """Get the route lists."""
        _LOGGER.warning("async_get_route")

        # Get /route
        return await self._async_request(self._api.async_get_route())

    async def async_post_client_certificate(
        self, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Post the client certificate request."""
        _LOGGER.warning("async_post_client_certificate")

        # POST /client/certificate
        return await self._async_request(
            self._api.async_post_client_certificate(json=body)
        )

    async def async_get_push_list(self) -> dict[str, Any] | None:
        """Get the push device lists."""
        _LOGGER.warning("async_get_push_list")

        # Get /push
        return await self._async_request(self._api.async_get_push_list())

    async def async_post_push_subscribe(
        self, device_id: str
    ) -> dict[str, Any] | None:
        """Subscribe the push for the given device id."""
        _LOGGER.debug("async_post_push_subscribe. device_id=%s", device_id)

        # POST /push/{device-id}/subscribe
        return await self._async_request(
            self._api.async_post_push_subscribe(device_id=device_id)
        )

    async def async_delete_push_subscribe(
        self, device_id: str
    ) -> dict[str, Any] | None:
        """Unsubscribe the push for the given device id."""
        _LOGGER.warning("async_delete_push_subscribe. device_id=%s", device_id)

        # DELETE /push/{device_id}/unsubscribe
        return await self._async_request(
            self._api.async_delete_push_subscribe(device_id=device_id)
        )

    async def async_get_event_list(self) -> dict[str, Any] | None:
        """Get the event device lists."""
        _LOGGER.warning("async_get_event_list")

        # Get /event
        return await self._async_request(self._api.async_get_event_list())

    async def async_post_event_subscribe(
        self, device_id: str, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Subscribe the event for the given device id."""
        _LOGGER.debug("async_post_event_subscribe. device_id=%s", device_id)

        # POST /event/{device_id}/subscribe
        return await self._async_request(
            self._api.async_post_event_subscribe(device_id=device_id)
        )

    async def async_delete_event_subscribe(
        self, device_id: str
    ) -> dict[str, Any] | None:
        """Unsubscribe the event for the given device id."""
        _LOGGER.warning(
            "async_delete_event_subscribe. device_id=%s", device_id
        )

        # DELETE /event/{device_id}/unsubscribe
        return await self._async_request(
            self._api.async_delete_event_subscribe(device_id=device_id)
        )

    async def async_post_push_devices_subscribe(self) -> dict[str, Any] | None:
        """Subscribe the push for device addition, deletion, and modification."""
        _LOGGER.warning("async_post_push_devices_subscribe.")

        # POST /homes/push
        return await self._async_request(
            self._api.async_post_push_devices_subscribe()
        )

    async def async_delete_push_devices_subscribe(
        self,
    ) -> dict[str, Any] | None:
        """Unsubscribe the push for device addition, deletion, and modification."""
        _LOGGER.warning("async_delete_push_devices_subscribe")

        # DELETE /homes/push
        return await self._async_request(
            self._api.async_delete_push_devices_subscribe()
        )
