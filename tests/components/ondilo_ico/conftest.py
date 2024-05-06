"""Provide basic Ondilo fixture."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.ondilo_ico.const import DOMAIN
from homeassistant.util.json import JsonArrayType, JsonObjectType

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Ondilo ICO",
        data={"auth_implementation": DOMAIN, "token": {"access_token": "fake_token"}},
    )


@pytest.fixture
def mock_ondilo_client(
    two_pools: JsonArrayType,
    ico_details1: JsonObjectType,
    ico_details2: JsonObjectType,
    last_measures: JsonArrayType,
) -> Generator[MagicMock, None, None]:
    """Mock a Homeassistant Ondilo client."""
    with (
        patch(
            "homeassistant.components.ondilo_ico.api.OndiloClient",
            autospec=True,
        ) as mock_ondilo,
    ):
        client = mock_ondilo.return_value
        client.get_pools.return_value = two_pools
        client.get_ICO_details.side_effect = [ico_details1, ico_details2]
        client.get_last_pool_measures.return_value = last_measures
        yield client


@pytest.fixture
def pool1() -> JsonArrayType:
    """First pool description."""
    return [load_json_object_fixture("pool1.json", "ondilo_ico")]


@pytest.fixture
def pool2() -> JsonArrayType:
    """Second pool description."""
    return [load_json_object_fixture("pool2.json", "ondilo_ico")]


@pytest.fixture
def ico_details1() -> JsonObjectType:
    """ICO details of first pool."""
    return load_json_object_fixture("ico_details1.json", "ondilo_ico")


@pytest.fixture
def ico_details2() -> JsonObjectType:
    """ICO details of second pool."""
    return load_json_object_fixture("ico_details2.json", "ondilo_ico")


@pytest.fixture
def last_measures() -> JsonArrayType:
    """Pool measurements."""
    return load_json_array_fixture("last_measures.json", "ondilo_ico")


@pytest.fixture
def two_pools() -> JsonArrayType:
    """Two pools description."""
    pool1 = load_json_object_fixture("pool1.json", "ondilo_ico")
    pool2 = load_json_object_fixture("pool2.json", "ondilo_ico")
    return [pool1, pool2]
