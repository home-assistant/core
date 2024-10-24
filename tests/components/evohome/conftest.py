"""Fixtures and helpers for the evohome tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timedelta, timezone
from http import HTTPMethod
from typing import Any
from unittest.mock import MagicMock, patch

from aiohttp import ClientSession
from evohomeasync2 import EvohomeClient
from evohomeasync2.broker import Broker
import pytest

from homeassistant.components.evohome import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .const import ACCESS_TOKEN, REFRESH_TOKEN, USERNAME

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


def mock_get_factory(install: str) -> Callable:
    """Return a get method for a specified installation."""

    async def mock_get(
        self: Broker, url: str, **kwargs: Any
    ) -> JsonArrayType | JsonObjectType:
        """Return the JSON for a HTTP get of a given URL."""

        # a proxy for the behaviour of the real web API
        if self.refresh_token is None:
            self.refresh_token = f"new_{REFRESH_TOKEN}"

        if (
            self.access_token_expires is None
            or self.access_token_expires < datetime.now()
        ):
            self.access_token = f"new_{ACCESS_TOKEN}"
            self.access_token_expires = datetime.now() + timedelta(minutes=30)

        # assume a valid GET, and return the JSON for that web API
        if url == "userAccount":  # userAccount
            return user_account_config_fixture(install)

        if url.startswith("location"):
            if "installationInfo" in url:  # location/installationInfo?userId={id}
                return user_locations_config_fixture(install)
            if "location" in url:  # location/{id}/status
                return location_status_fixture(install)

        elif "schedule" in url:
            if url.startswith("domesticHotWater"):  # domesticHotWater/{id}/schedule
                return dhw_schedule_fixture(install)
            if url.startswith("temperatureZone"):  # temperatureZone/{id}/schedule
                return zone_schedule_fixture(install)

        pytest.fail(f"Unexpected request: {HTTPMethod.GET} {url}")

    return mock_get


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
        patch("homeassistant.components.evohome.evo.EvohomeClient") as mock_client,
        patch("homeassistant.components.evohome.ev1.EvohomeClient", return_value=None),
        patch("evohomeasync2.broker.Broker.get", mock_get_factory(install)),
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

        assert mock_client.call_args.args[0] == config[CONF_USERNAME]
        assert mock_client.call_args.args[1] == config[CONF_PASSWORD]

        assert isinstance(mock_client.call_args.kwargs["session"], ClientSession)

        assert evo and evo.account_info is not None

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
