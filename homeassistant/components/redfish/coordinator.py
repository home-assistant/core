"""Data coordinator for Redfish."""

import asyncio
from dataclasses import replace
import logging
from typing import Any, override

import aiohttp
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BASE_URL, DOMAIN, REQUEST_TIMEOUT, UPDATE_INTERVAL
from .models import (
    RedfishData,
    RedfishSystem,
    get_reset_action_info_target,
    parse_reset_action_info,
    parse_system,
)

_LOGGER = logging.getLogger(__name__)

type RedfishConfigEntry = ConfigEntry[RedfishDataUpdateCoordinator]


class RedfishError(Exception):
    """Base error communicating with Redfish."""


class RedfishAuthError(RedfishError):
    """Authentication failed."""


class RedfishClient:
    """Minimal asynchronous Redfish client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = URL(base_url)
        self._headers = {"Authorization": aiohttp.encode_basic_auth(username, password)}

    def _resolve_url(self, target: str) -> URL:
        """Resolve a Redfish target and require the configured origin."""
        target_url = self._base_url.join(URL(target))
        if target_url.origin() != self._base_url.origin():
            raise RedfishError
        return target_url

    async def _async_get(self, path: str) -> dict[str, Any]:
        """Get a Redfish resource."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(
                    self._resolve_url(path),
                    allow_redirects=False,
                    headers=self._headers,
                ) as response:
                    self._check_response(response)
                    payload = await response.json()
        except RedfishAuthError:
            raise
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise RedfishError from err
        if not isinstance(payload, dict):
            raise RedfishError
        return payload

    async def async_reset(self, target: str, reset_type: str) -> None:
        """Perform an advertised reset action."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.post(
                    self._resolve_url(target),
                    allow_redirects=False,
                    headers=self._headers,
                    json={"ResetType": reset_type},
                ) as response:
                    self._check_response(response)
        except RedfishAuthError:
            raise
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise RedfishError from err

    async def async_get_systems(self) -> dict[str, RedfishSystem]:
        """Discover ComputerSystem resources from the service root."""
        root = await self._async_get("/redfish/v1/")
        return await self._async_systems(root.get("Systems"))

    async def async_discover(self) -> RedfishData:
        """Discover ComputerSystem resources."""
        root = await self._async_get("/redfish/v1/")
        systems = await self._async_systems(root.get("Systems"))
        return RedfishData(systems)

    async def _async_systems(self, link: Any) -> dict[str, RedfishSystem]:
        """Resolve and parse ComputerSystem resources."""
        systems = {}
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
    def _check_response(response: aiohttp.ClientResponse) -> None:
        """Validate a Redfish response."""
        if response.status in (401, 403):
            raise RedfishAuthError
        if not 200 <= response.status < 300:
            raise RedfishError


class RedfishDataUpdateCoordinator(DataUpdateCoordinator[RedfishData]):
    """Coordinate Redfish polling."""

    config_entry: RedfishConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RedfishConfigEntry) -> None:
        """Initialize coordinator."""
        self.client = RedfishClient(
            async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL]),
            entry.data[CONF_BASE_URL],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> RedfishData:
        """Fetch Redfish data."""
        try:
            return await self.client.async_discover()
        except RedfishError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err
