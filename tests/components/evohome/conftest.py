"""Fixtures and helpers for the evohome tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from datetime import timedelta, timezone
from http import HTTPMethod
from typing import Any
from unittest.mock import MagicMock, patch

from evohomeasync2 import EvohomeClient
from evohomeasync2.auth import AbstractTokenManager, Auth
from evohomeasync2.control_system import ControlSystem
from evohomeasync2.zone import Zone
import pytest

from homeassistant.components.evohome.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .const import ACCESS_TOKEN, REFRESH_TOKEN, SESSION_ID, USERNAME

from tests.common import load_json_array_fixture, load_json_object_fixture


def user_account_config_fixture(install: str) -> JsonObjectType:
    """Load JSON for the config of a user's account."""
    try:
        return load_json_object_fixture(f"{install}/user_account.json", DOMAIN)
    except FileNotFoundError:
        return load_json_object_fixture("default/user_account.json", DOMAIN)


def user_locations_config_fixture(install: str) -> JsonArrayType:
    """Load JSON for the config of a user's installation (a list of locations)."""
    return load_json_array_fixture(f"{install}/user_locations.json", DOMAIN)


def location_status_fixture(install: str, loc_id: str | None = None) -> JsonObjectType:
    """Load JSON for the status of a specific location."""
    if loc_id is None:
        _install = load_json_array_fixture(f"{install}/user_locations.json", DOMAIN)
        loc_id = _install[0]["locationInfo"]["locationId"]  # type: ignore[assignment, call-overload, index]
    return load_json_object_fixture(f"{install}/status_{loc_id}.json", DOMAIN)


def dhw_schedule_fixture(install: str) -> JsonObjectType:
    """Load JSON for the schedule of a domesticHotWater zone."""
    try:
        return load_json_object_fixture(f"{install}/schedule_dhw.json", DOMAIN)
    except FileNotFoundError:
        return load_json_object_fixture("default/schedule_dhw.json", DOMAIN)


def zone_schedule_fixture(install: str) -> JsonObjectType:
    """Load JSON for the schedule of a temperatureZone zone."""
    try:
        return load_json_object_fixture(f"{install}/schedule_zone.json", DOMAIN)
    except FileNotFoundError:
        return load_json_object_fixture("default/schedule_zone.json", DOMAIN)


def mock_post_request(install: str) -> Callable:
    """Obtain an access token via a POST to the vendor's web API."""

    async def post_request(
        self: AbstractTokenManager, url: str, /, **kwargs: Any
    ) -> JsonArrayType | JsonObjectType:
        """Obtain an access token via a POST to the vendor's web API."""

        if "Token" in url:
            return {
                "access_token": f"new_{ACCESS_TOKEN}",
                "token_type": "bearer",
                "expires_in": 1800,
                "refresh_token": f"new_{REFRESH_TOKEN}",
                # "scope": "EMEA-V1-Basic EMEA-V1-Anonymous",  # optional
            }

        if "session" in url:
            return {"sessionId": f"new_{SESSION_ID}"}

        pytest.fail(f"Unexpected request: {HTTPMethod.POST} {url}")

    return post_request


def mock_make_request(install: str) -> Callable:
    """Return a get method for a specified installation."""

    async def make_request(
        self: Auth, method: HTTPMethod, url: str, **kwargs: Any
    ) -> JsonArrayType | JsonObjectType:
        """Return the JSON for a HTTP get of a given URL."""

        if method != HTTPMethod.GET:
            pytest.fail(f"Unmocked method: {method} {url}")

        await self._headers()

        # assume a valid GET, and return the JSON for that web API
        if url == "userAccount":  # /userAccount
            return user_account_config_fixture(install)

        if url.startswith("location/"):
            if "installationInfo" in url:  # /location/installationInfo?userId={id}
                return user_locations_config_fixture(install)
            if "status" in url:  # /location/{id}/status
                return location_status_fixture(install)

        elif "schedule" in url:
            if url.startswith("domesticHotWater"):  # /domesticHotWater/{id}/schedule
                return dhw_schedule_fixture(install)
            if url.startswith("temperatureZone"):  # /temperatureZone/{id}/schedule
                return zone_schedule_fixture(install)

        pytest.fail(f"Unexpected request: {HTTPMethod.GET} {url}")

    return make_request


@pytest.fixture
def config() -> dict[str, str]:
    "Return a default/minimal configuration."
    return {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: "password",
    }


async def setup_evohome(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str = "default",
) -> AsyncGenerator[MagicMock]:
    """Set up the evohome integration and return its client.

    The class is mocked here to check the client was instantiated with the correct args.
    """

    # set the time zone as for the active evohome location
    loc_idx: int = config.get("location_idx", 0)  # type: ignore[assignment]

    try:
        locn = user_locations_config_fixture(install)[loc_idx]
    except IndexError:
        if loc_idx == 0:
            raise
        locn = user_locations_config_fixture(install)[0]

    utc_offset: int = locn["locationInfo"]["timeZone"]["currentOffsetMinutes"]  # type: ignore[assignment, call-overload, index]
    dt_util.set_default_time_zone(timezone(timedelta(minutes=utc_offset)))

    with (
        # patch("homeassistant.components.evohome.ec1.EvohomeClient", return_value=None),
        patch("homeassistant.components.evohome.ec2.EvohomeClient") as mock_client,
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request(install),
        ),
        patch("evohomeasync2.auth.Auth._make_request", mock_make_request(install)),
    ):
        evo: EvohomeClient | None = None

        def evohome_client(*args, **kwargs) -> EvohomeClient:
            nonlocal evo
            evo = EvohomeClient(*args, **kwargs)
            return evo

        mock_client.side_effect = evohome_client

        assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()

        mock_client.assert_called_once()

        assert isinstance(evo, EvohomeClient)
        assert evo._token_manager.client_id == config[CONF_USERNAME]
        assert evo._token_manager._secret == config[CONF_PASSWORD]

        assert evo.user_account

        mock_client.return_value = evo
        yield mock_client


@pytest.fixture
async def evohome(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
) -> AsyncGenerator[MagicMock]:
    """Return the mocked evohome client for this install fixture."""

    async for mock_client in setup_evohome(hass, config, install=install):
        yield mock_client


@pytest.fixture
async def ctl_id(
    hass: HomeAssistant,
    config: dict[str, str],
    install: MagicMock,
) -> AsyncGenerator[str]:
    """Return the entity_id of the evohome integration's controller."""

    async for mock_client in setup_evohome(hass, config, install=install):
        evo: EvohomeClient = mock_client.return_value
        ctl: ControlSystem = evo.tcs

        yield f"{Platform.CLIMATE}.{slugify(ctl.location.name)}"


@pytest.fixture
async def zone_id(
    hass: HomeAssistant,
    config: dict[str, str],
    install: MagicMock,
) -> AsyncGenerator[str]:
    """Return the entity_id of the evohome integration's first zone."""

    async for mock_client in setup_evohome(hass, config, install=install):
        evo: EvohomeClient = mock_client.return_value
        zone: Zone = evo.tcs.zones[0]

        yield f"{Platform.CLIMATE}.{slugify(zone.name)}"
