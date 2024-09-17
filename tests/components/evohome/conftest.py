"""Fixtures and helpers for the evohome tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timedelta, timezone
from http import HTTPMethod
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from aiohttp import ClientSession
from evohomeasync2 import EvohomeClient
from evohomeasync2.broker import Broker
import pytest

from homeassistant.components.evohome import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    EvoBroker,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .const import ACCESS_TOKEN, REFRESH_TOKEN, USERNAME

from tests.common import load_json_array_fixture, load_json_object_fixture

if TYPE_CHECKING:
    from homeassistant.components.evohome.climate import EvoController, EvoZone
    from homeassistant.components.evohome.water_heater import EvoDHW


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


async def block_request(
    self: Broker, method: HTTPMethod, url: str, **kwargs: Any
) -> None:
    """Fail if the code attempts any actual I/O via aiohttp."""

    pytest.fail(f"Unexpected request: {method} {url}")


@pytest.fixture(scope="module")
def config() -> dict[str, str]:
    "Return a default/minimal configuration."
    return {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: "password",
    }


async def setup_evohome(
    hass: HomeAssistant,
    test_config: dict[str, str],
    install: str = "default",
) -> AsyncGenerator[MagicMock]:
    """Mock the evohome integration and return its client.

    The class is mocked here to check the client was instantiated with the correct args.
    """

    with (
        patch("homeassistant.components.evohome.evo.EvohomeClient") as mock_client,
        patch("homeassistant.components.evohome.ev1.EvohomeClient", return_value=None),
        patch("evohomeasync2.broker.Broker.get", mock_get_factory(install)),
    ):
        mock_client.side_effect = EvohomeClient

        assert await async_setup_component(hass, DOMAIN, {DOMAIN: test_config})
        await hass.async_block_till_done()

        mock_client.assert_called_once()

        assert mock_client.call_args.args[0] == test_config[CONF_USERNAME]
        assert mock_client.call_args.args[1] == test_config[CONF_PASSWORD]

        assert isinstance(mock_client.call_args.kwargs["session"], ClientSession)

        assert mock_client.account_info is not None

        broker: EvoBroker = hass.data[DOMAIN]["broker"]
        dt_util.set_default_time_zone(timezone(broker.loc_utc_offset))

        try:
            yield mock_client
        finally:
            # wait for DataUpdateCoordinator to quiesce
            await hass.async_block_till_done()


def entity_of_ctl(hass: HomeAssistant) -> EvoController:
    """Return the controller entity of the evohome system."""

    broker: EvoBroker = hass.data[DOMAIN]["broker"]

    entity_registry = er.async_get(hass)

    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, broker.tcs._id
    )
    return entity_registry.async_get(entity_id)


def entity_of_dhw(hass: HomeAssistant) -> EvoDHW | None:
    """Return the DHW entity of the evohome system."""

    broker: EvoBroker = hass.data[DOMAIN]["broker"]

    if (dhw := broker.tcs.hotwater) is None:
        return None

    entity_registry = er.async_get(hass)

    entity_id = entity_registry.async_get_entity_id(
        Platform.WATER_HEATER, DOMAIN, dhw._id
    )
    return entity_registry.async_get(entity_id)


def entity_of_zone(hass: HomeAssistant) -> EvoZone:
    """Return the entity of the first zone of the evohome system."""

    broker: EvoBroker = hass.data[DOMAIN]["broker"]

    unique_id = broker.tcs._zones[0]._id
    if unique_id == broker.tcs._id:
        unique_id += "z"  # special case of merged controller/zone

    entity_registry = er.async_get(hass)

    entity_id = entity_registry.async_get_entity_id(Platform.CLIMATE, DOMAIN, unique_id)
    return entity_registry.async_get(entity_id)
