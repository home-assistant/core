"""Tests for the pvpc_hourly_pricing integration."""
import pytest

from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF, DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CURRENCY_EURO,
    ENERGY_KILO_WATT_HOUR,
)

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

FIXTURE_JSON_DATA_2019_10_26 = "PVPC_CURV_DD_2019_10_26.json"
FIXTURE_JSON_DATA_2019_10_27 = "PVPC_CURV_DD_2019_10_27.json"
FIXTURE_JSON_DATA_2019_10_29 = "PVPC_CURV_DD_2019_10_29.json"


def check_valid_state(state, tariff: str, value=None, key_attr=None):
    """Ensure that sensor has a valid state and attributes."""
    assert state
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}"
    )
    try:
        _ = float(state.state)
        # safety margins for current electricity price (it shouldn't be out of [0, 0.2])
        assert -0.1 < float(state.state) < 0.3
        assert state.attributes[ATTR_TARIFF] == tariff
    except ValueError:
        pass

    if value is not None and isinstance(value, str):
        assert state.state == value
    elif value is not None:
        assert abs(float(state.state) - value) < 1e-6
    if key_attr is not None:
        assert abs(float(state.state) - state.attributes[key_attr]) < 1e-6


@pytest.fixture
def pvpc_aioclient_mock(aioclient_mock: AiohttpClientMocker):
    """Create a mock config entry."""
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-10-26",
        text=load_fixture(f"{DOMAIN}/{FIXTURE_JSON_DATA_2019_10_26}"),
    )
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-10-27",
        text=load_fixture(f"{DOMAIN}/{FIXTURE_JSON_DATA_2019_10_27}"),
    )
    # missing day
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-10-28",
        text='{"message":"No values for specified archive"}',
    )
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-10-29",
        text=load_fixture(f"{DOMAIN}/{FIXTURE_JSON_DATA_2019_10_29}"),
    )

    return aioclient_mock
