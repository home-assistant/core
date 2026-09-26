"""Redfish API adapter."""

import asyncio
from dataclasses import replace
from typing import Any

import aiohttp
from redfish.aio import (
    AsyncRedfishClient,
    RedfishAuthenticationError,
    RedfishError as RedfishLibraryError,
)

from .const import COLLECTION_TIMEOUT, REQUEST_TIMEOUT
from .models import (
    RedfishData,
    RedfishSystem,
    get_reset_action_info_target,
    parse_reset_action_info,
    parse_system,
)


class RedfishError(Exception):
    """Base error communicating with Redfish."""


class RedfishAuthError(RedfishError):
    """Authentication failed."""


class RedfishApi:
    """Adapt the generic Redfish client for Home Assistant."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the API adapter."""
        self._client = AsyncRedfishClient(
            base_url=base_url,
            username=username,
            password=password,
            session=session,
            timeout=REQUEST_TIMEOUT,
        )

    async def async_login(self) -> None:
        """Configure HTTP Basic authentication."""
        try:
            await self._client.login(auth="basic")
        except RedfishAuthenticationError as err:
            raise RedfishAuthError from err
        except RedfishLibraryError as err:
            raise RedfishError from err

    async def async_logout(self) -> None:
        """Clear Redfish authentication state."""
        try:
            await self._client.logout()
        except RedfishAuthenticationError as err:
            raise RedfishAuthError from err
        except RedfishLibraryError as err:
            raise RedfishError from err

    async def _async_get(self, path: str) -> dict[str, Any]:
        """Get a Redfish resource."""
        try:
            response = await self._client.get(path)
            self._check_response(response.status)
            payload = response.dict
        except RedfishAuthError:
            raise
        except RedfishAuthenticationError as err:
            raise RedfishAuthError from err
        except RedfishLibraryError as err:
            raise RedfishError from err
        if not isinstance(payload, dict):
            raise RedfishError
        return payload

    async def async_reset(self, target: str, reset_type: str) -> None:
        """Perform an advertised reset action."""
        try:
            response = await self._client.post(target, body={"ResetType": reset_type})
        except RedfishAuthenticationError as err:
            raise RedfishAuthError from err
        except RedfishLibraryError as err:
            raise RedfishError from err
        self._check_response(response.status)

    async def async_get_systems(self) -> dict[str, RedfishSystem]:
        """Discover ComputerSystem resources from the service root."""
        root = await self._async_get("/redfish/v1/")
        return await self._async_systems(root.get("Systems"))

    async def async_discover(self) -> RedfishData:
        """Discover Redfish resources."""
        return RedfishData(await self.async_get_systems())

    async def _async_systems(self, link: Any) -> dict[str, RedfishSystem]:
        """Resolve and parse ComputerSystem resources."""
        systems = {}
        try:
            async with asyncio.timeout(COLLECTION_TIMEOUT):
                for payload in await self._async_members(link):
                    if system := parse_system(payload):
                        if system.reset_target is not None and (
                            action_info_target := get_reset_action_info_target(payload)
                        ):
                            action_info = await self._async_get(action_info_target)
                            system = replace(
                                system,
                                reset_types=system.reset_types
                                | parse_reset_action_info(action_info),
                            )
                        systems[system.system_id] = system
        except TimeoutError as err:
            raise RedfishError from err
        return systems

    async def _async_members(self, link: Any) -> list[dict[str, Any]]:
        """Resolve a Redfish collection's member resources."""
        if (
            not isinstance(link, dict)
            or not isinstance(path := link.get("@odata.id"), str)
            or not path.strip()
        ):
            return []
        payloads = []
        seen_paths = set[str]()
        while True:
            if path in seen_paths:
                raise RedfishError
            seen_paths.add(path)
            collection = await self._async_get(path)
            members = collection.get("Members")
            if not isinstance(members, list):
                return []
            payloads.extend(
                [
                    await self._async_get(member_path)
                    for member in members
                    if isinstance(member, dict)
                    and isinstance(member_path := member.get("@odata.id"), str)
                    and member_path.strip()
                ]
            )
            next_path = collection.get("Members@odata.nextLink")
            if not isinstance(next_path, str) or not next_path.strip():
                return payloads
            path = next_path

    @staticmethod
    def _check_response(status: int) -> None:
        """Validate a Redfish response status."""
        if status in (401, 403):
            raise RedfishAuthError
        if not 200 <= status < 300:
            raise RedfishError
