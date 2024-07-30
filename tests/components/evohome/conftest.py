"""Fixtures and helpers for the evohome tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any, Final
from unittest.mock import MagicMock, patch

from aiohttp import ClientSession
from evohomeasync2 import EvohomeClient
from evohomeasync2.broker import Broker
import pytest

from homeassistant.components.evohome import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .const import ACCESS_TOKEN, REFRESH_TOKEN

from tests.common import load_json_array_fixture, load_json_object_fixture

TEST_CONFIG: Final = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}


def user_account_config_fixture() -> JsonObjectType:
    """Load JSON for the config of a user's account."""
    return load_json_object_fixture("user_account.json", DOMAIN)


def user_locations_config_fixture() -> JsonArrayType:
    """Load JSON for the config of a user's installation (a list of locations)."""
    return load_json_array_fixture("user_locations.json", DOMAIN)


def location_status_fixture(loc_id: str) -> JsonObjectType:
    """Load JSON for the status of a specific location."""
    return load_json_object_fixture(f"status_{loc_id}.json", DOMAIN)


def dhw_schedule_fixture() -> JsonObjectType:
    """Load JSON for the schedule of a domesticHotWater zone."""
    return load_json_object_fixture("schedule_dhw.json", DOMAIN)


def zone_schedule_fixture() -> JsonObjectType:
    """Load JSON for the schedule of a temperatureZone zone."""
    return load_json_object_fixture("schedule_zone.json", DOMAIN)


async def mock_get(
    self: Broker, url: str, **kwargs: Any
) -> JsonArrayType | JsonObjectType:
    """Return the JSON for a HTTP get of a given URL."""

    # a proxy for the behaviour of the real web API
    if self.refresh_token is None:
        self.refresh_token = f"new_{REFRESH_TOKEN}"

    if self.access_token_expires is None or self.access_token_expires < datetime.now():
        self.access_token = f"new_{ACCESS_TOKEN}"
        self.access_token_expires = datetime.now() + timedelta(minutes=30)

    # assume a valid GET, and return the JSON for that web API
    if url == "userAccount":  #                    userAccount
        return user_account_config_fixture()

    if url.startswith("location"):
        if "installationInfo" in url:  #           location/installationInfo?userId={id}
            return user_locations_config_fixture()
        if "location" in url:  #                   location/{id}/status
            return location_status_fixture("2738909")

    elif "schedule" in url:
        if url.startswith("domesticHotWater"):  #  domesticHotWater/{id}/schedule
            return dhw_schedule_fixture()
        if url.startswith("temperatureZone"):  #   temperatureZone/{id}/schedule
            return zone_schedule_fixture()

    pytest.xfail(f"Unexpected URL: {url}")


async def _setup_evohome(
    hass: HomeAssistant, test_config: dict[str, str]
) -> tuple[HomeAssistant, MagicMock]:
    mock_client: EvohomeClient | None = None

    def capture_client(*args: Any, **kwargs: Any):
        nonlocal mock_client
        mock_client = EvohomeClient(*args, **kwargs)
        return mock_client

    with (
        patch(
            "homeassistant.components.evohome.evo.EvohomeClient",
            side_effect=capture_client,
        ) as mock_class,
        patch("evohomeasync2.broker.Broker.get", mock_get),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: test_config})
        await hass.async_block_till_done()

        mock_class.assert_called_once()
        assert mock_class.call_args.args[0] == test_config[CONF_USERNAME]
        assert mock_class.call_args.args[1] == test_config[CONF_PASSWORD]

        assert isinstance(mock_class.call_args.kwargs["session"], ClientSession)
        assert mock_client and mock_client.account_info is not None

        return hass, mock_class


async def evo_client(hass: HomeAssistant, test_config: dict[str, str]) -> MagicMock:
    """Return the EvohomeClient instantiated via the Evohome integration."""

    return (await _setup_evohome(hass, test_config))[1]


@pytest.fixture
async def evo_hass(hass: HomeAssistant) -> AsyncGenerator[HomeAssistant]:
    """Return an instance of Home Assistant with an Evohome integration."""

    hass, _ = await _setup_evohome(hass, TEST_CONFIG)

    yield hass  # noqa: PT022
