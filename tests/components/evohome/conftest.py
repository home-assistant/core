"""Fixtures and helpers for the evohome tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from datetime import timedelta, timezone
from http import HTTPMethod
from typing import Any
from unittest.mock import MagicMock, patch

import evohomeasync2 as ec2
from evohomeasync2 import EvohomeClient
from evohomeasync2.auth import AbstractTokenManager, Auth
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.evohome import CONFIG_SCHEMA
from homeassistant.components.evohome.config_flow import EvoConfigFileDictT
from homeassistant.components.evohome.const import (
    CONF_HIGH_PRECISION,
    CONF_LOCATION_IDX,
    DEFAULT_LOCATION_IDX,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .const import ACCESS_TOKEN, REFRESH_TOKEN, SESSION_ID, USERNAME

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

_DEFAULT_INSTALL = "default"


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


def dhw_schedule_fixture(install: str, dhw_id: str | None = None) -> JsonObjectType:
    """Load JSON for the schedule of a domesticHotWater zone."""
    try:
        return load_json_object_fixture(f"{install}/schedule_{dhw_id}.json", DOMAIN)
    except FileNotFoundError:
        return load_json_object_fixture("default/schedule_dhw.json", DOMAIN)


def zone_schedule_fixture(install: str, zon_id: str | None = None) -> JsonObjectType:
    """Load JSON for the schedule of a temperatureZone zone."""
    try:
        return load_json_object_fixture(f"{install}/schedule_{zon_id}.json", DOMAIN)
    except FileNotFoundError:
        return load_json_object_fixture("default/schedule_zone.json", DOMAIN)


def mock_post_request(install: str) -> Callable:
    """Return a HTTP POST method that acts for a specified installation.

    Used to validate user credentials and return the access token / session ID.
    """

    async def post_request(
        self: AbstractTokenManager, url: str, /, **kwargs: Any
    ) -> JsonArrayType | JsonObjectType:
        """Validate user credentials and return the access token / session ID."""

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
    """Return a HTTP request method that acts for a specified installation.

    Used to process a given request to return the corresponding JSON.
    """

    async def make_request(
        self: Auth, method: HTTPMethod, url: str, **kwargs: Any
    ) -> JsonArrayType | JsonObjectType:
        """Process a given request to return the corresponding JSON."""

        if method != HTTPMethod.GET:
            pytest.fail(f"Unmocked method: {method} {url}")

        await self._headers()

        # assume GET is valid, and return the JSON for that web API
        if url == "accountInfo":  # v0, accountInfo
            return {}  # will throw a KeyError -> BadApiResponseError

        if url.startswith("locations/"):  # v0, locations?userId={id}&allData=True
            return []  # user has no locations

        if url == "userAccount":  # v2, userAccount
            return user_account_config_fixture(install)

        if url.startswith("location/"):
            if "installationInfo" in url:  # v2, location/installationInfo?userId={id}
                return user_locations_config_fixture(install)
            if "status" in url:  # v2, location/{id}/status
                return location_status_fixture(install)

        elif "schedule" in url:
            if url.startswith("domesticHotWater"):  # v2, domesticHotWater/{id}/schedule
                return dhw_schedule_fixture(install, url.split("/")[1])
            if url.startswith("temperatureZone"):  # v2, temperatureZone/{id}/schedule
                return zone_schedule_fixture(install, url.split("/")[1])

        pytest.fail(f"Unexpected request: {HTTPMethod.GET} {url}")

    return make_request


@pytest.fixture
def config() -> EvoConfigFileDictT:
    "Return a default/minimal configuration."
    config = {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: "P@ssw0rd",
        CONF_LOCATION_IDX: DEFAULT_LOCATION_IDX,
        CONF_SCAN_INTERVAL: timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    }
    return CONFIG_SCHEMA({DOMAIN: config})[DOMAIN]


@pytest.fixture(name="config_entry")
def config_entry_fixture(config: EvoConfigFileDictT) -> MockConfigEntry:
    """Define a config entry fixture."""

    data = {k: v for k, v in config.items() if k != CONF_SCAN_INTERVAL}

    options = {
        CONF_HIGH_PRECISION: True,
        CONF_SCAN_INTERVAL: config[CONF_SCAN_INTERVAL].seconds,
    }

    return MockConfigEntry(
        title="Evohome",
        domain=DOMAIN,
        unique_id=config[CONF_USERNAME].lower(),
        data=data,
        options=options,
    )


async def setup_evohome(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str = _DEFAULT_INSTALL,
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
        patch(
            "homeassistant.components.evohome.coordinator.ec2.EvohomeClient"
        ) as mock_client,
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request(install),
        ),
        patch("evohome.auth.AbstractAuth._make_request", mock_make_request(install)),
    ):
        evo: ec2.EvohomeClient | None = None

        def evohome_client(*args, **kwargs) -> ec2.EvohomeClient:
            nonlocal evo
            evo = EvohomeClient(*args, **kwargs)  # NOTE: don't use ec2.EvohomeClient
            return evo

        mock_client.side_effect = evohome_client

        assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()

        mock_client.assert_called()  # called twice

        assert isinstance(evo, EvohomeClient)
        assert evo._token_manager.client_id == config[CONF_USERNAME]
        assert evo._token_manager._secret == config[CONF_PASSWORD]

        assert evo.user_account

        mock_client.return_value = evo
        yield mock_client


@pytest.fixture  # can instead: @pytest.mark.parametrize("install", ["default"])
def install() -> str:
    "Return a default/minimal installation."
    return _DEFAULT_INSTALL


@pytest.fixture
async def evohome(
    hass: HomeAssistant,
    config: dict[str, str],
    freezer: FrozenDateTimeFactory,
    install: str,
) -> AsyncGenerator[MagicMock]:
    """Return the mocked evohome client for this install fixture."""

    freezer.move_to("2024-07-10T12:00:00Z")  # so schedules are as expected

    async for mock_client in setup_evohome(hass, config, install=install):
        yield mock_client


@pytest.fixture
def ctl_id(evohome: MagicMock) -> str:
    """Return the entity_id of the evohome integration's controller."""

    evo: ec2.EvohomeClient = evohome.return_value
    ctl: ec2.ControlSystem = evo.tcs

    return f"{Platform.CLIMATE}.{slugify(ctl.location.name)}"


@pytest.fixture
def zone_id(evohome: MagicMock) -> str:
    """Return the entity_id of the evohome integration's first zone."""

    evo: ec2.EvohomeClient = evohome.return_value
    zone: ec2.Zone = evo.tcs.zones[0]

    return f"{Platform.CLIMATE}.{slugify(zone.name)}"
