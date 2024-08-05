"""Fixtures and helpers for the evohome tests."""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import datetime, timedelta
import logging
from typing import Any, Final, TypedDict
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

_LOGGER = logging.getLogger(__name__)


DEFAULT_TEST_CONFIG: Final = {
    "username": "username",
    "password": "password",
}


class ResultSet(TypedDict):
    """A type for the expected state of the evohome integration."""

    tcs: dict[str, dict[str, Any]]  # always 1 value
    zones: dict[str, dict[str, Any]]  # 1-many values
    dhw: dict[str, Any]  # 0 or 1 values
    services: list[str]


class ExpectedResults:
    """A class to hold the expected state of the evohome integration."""

    def __init__(self, hass: HomeAssistant, expected: ResultSet) -> None:
        """Initialize the database of expected states/services."""

        # will assert against hass.states, and hass.services
        self._hass = hass

        # expected entity states, services
        self.entities = {
            i: j for k in ("tcs", "zones", "dhw") for i, j in expected[k].items()
        }

        self.tcs = list(expected["tcs"].keys())[0]
        self.zones = list(expected["zones"].keys())
        if dhws := expected.get("dhw"):
            self.dhw = list(dhws.keys())[0]
        else:
            self.dhw = None

        # c.f. hass.services.async_services_for_domain(DOMAIN)
        self.services = expected["services"]

    def assert_entities(self) -> None:
        """Assert that the actual entity ids are as expected."""
        # c.f. hass.states.async_entity_ids().

        assert set(self._hass.states.async_entity_ids()) == set(self.entities)

    def assert_entity_state(self, entity_id: str) -> bool:
        """Assert the entity was expected and state attrs match."""
        # c.f. hass.states.get(entity_id)
        # c.f. hass.states.is_state(entity_id, state)

        entity = self._hass.states.get(entity_id)

        try:
            for attr, value in self.entities[entity_id].items():
                try:
                    assert (
                        getattr(entity, attr) == value
                    ), f"{attr} is {entity.attributes[attr]}"
                except AttributeError:
                    assert (
                        entity.attributes[attr] == value
                    ), f"{attr} is {entity.attributes[attr]}"
        except AssertionError:
            expected = {
                "state": entity.state,
                "current_temperature": entity.attributes["current_temperature"],
                # "temperature": entity.attributes["temperature"],
            }
            for k in ("away_mode", "operation_mode", "preset_mode"):
                if k in entity.attributes:
                    expected[k] = entity.attributes[k]

            _LOGGER.warning("Expected state for %s was: %s", entity_id, expected)
            raise

    def assert_services(self) -> None:
        """Assert the actual services are as expected."""
        # c.f. hass.services.async_services_for_domain(DOMAIN)

        assert set(self._hass.services.async_services_for_domain(DOMAIN)) == set(
            self.services
        )


def expected_results_fixture(install: str) -> ExpectedResults:
    """Load the expected results for an installation."""
    return load_json_object_fixture(f"{install}/expected_results.json", DOMAIN)


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
        loc_id = _install[0]["locationInfo"]["locationId"]
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


def mock_get_factory(install: str) -> Awaitable:
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

        pytest.xfail(f"Unexpected URL: {url}")

    return mock_get


def mock_put_factory() -> Awaitable:
    """Return a get method for a specified installation."""

    async def mock_put(self: Broker, url: str, **kwargs: Any) -> None:
        """Effect the action for a HTTP put of a given URL."""

        if url == "userAccount":  # userAccount
            return

        pytest.xfail(f"Unexpected URL: {url}")

    return mock_put


async def setup_evohome(
    hass: HomeAssistant,
    test_config: dict[str, str] | None = None,
    installation: str = "default",
) -> MagicMock:
    """Set up the evohome integration and return its client.

    The class is mocked here to check the client was instantiated with the correct args.
    """

    if test_config is None:
        test_config = DEFAULT_TEST_CONFIG

    with (
        patch("homeassistant.components.evohome.evo.EvohomeClient") as mock_client,
        patch("homeassistant.components.evohome.ev1.EvohomeClient", return_value=None),
        patch("evohomeasync2.broker.Broker.get", mock_get_factory(installation)),
        patch("evohomeasync2.broker.Broker.put", mock_put_factory()),
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
