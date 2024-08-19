"""Fixtures and helpers for the evohome tests."""

from __future__ import annotations

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


@patch("evohomeasync2.broker.Broker.get", mock_get)
async def setup_evohome(hass: HomeAssistant, test_config: dict[str, str]) -> MagicMock:
    """Set up the evohome integration and return its client.

    The class is mocked here to check the client was instantiated with the correct args.
    """

    with (
        patch("homeassistant.components.evohome.evo.EvohomeClient") as mock_client,
        patch("homeassistant.components.evohome.ev1.EvohomeClient", return_value=None),
    ):
        mock_client.side_effect = EvohomeClient

        assert await async_setup_component(hass, DOMAIN, {DOMAIN: test_config})
        await hass.async_block_till_done()

        mock_client.assert_called_once()

        assert mock_client.call_args.args[0] == test_config[CONF_USERNAME]
        assert mock_client.call_args.args[1] == test_config[CONF_PASSWORD]

        assert isinstance(mock_client.call_args.kwargs["session"], ClientSession)

        assert mock_client.account_info is not None

        return mock_client
