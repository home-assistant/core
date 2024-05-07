"""Provide basic Ondilo fixture."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.ondilo_ico.const import (
    DOMAIN,
    OAUTH2_CLIENTID,
    OAUTH2_CLIENTSECRET,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(OAUTH2_CLIENTID, OAUTH2_CLIENTSECRET),
    )


@pytest.fixture
def mock_ondilo_client(
    two_pools: list[dict[str, Any]],
    ico_details1: dict[str, Any],
    ico_details2: dict[str, Any],
    last_measures: list[dict[str, Any]],
) -> Generator[MagicMock, None, None]:
    """Mock a Homeassistant Ondilo client."""
    with (
        patch(
            "homeassistant.components.ondilo_ico.OndiloClient",
            autospec=True,
        ) as mock_ondilo,
    ):
        client = mock_ondilo.return_value
        client.get_pools.return_value = two_pools
        client.get_ICO_details.side_effect = [ico_details1, ico_details2]
        client.get_last_pool_measures.return_value = last_measures
        yield client


@pytest.fixture(scope="session")
def pool1() -> list[dict[str, Any]]:
    """First pool description."""
    return [load_json_object_fixture("pool1.json", DOMAIN)]


@pytest.fixture(scope="session")
def pool2() -> list[dict[str, Any]]:
    """Second pool description."""
    return [load_json_object_fixture("pool2.json", DOMAIN)]


@pytest.fixture(scope="session")
def ico_details1() -> dict[str, Any]:
    """ICO details of first pool."""
    return load_json_object_fixture("ico_details1.json", DOMAIN)


@pytest.fixture(scope="session")
def ico_details2() -> dict[str, Any]:
    """ICO details of second pool."""
    return load_json_object_fixture("ico_details2.json", DOMAIN)


@pytest.fixture(scope="session")
def last_measures() -> list[dict[str, Any]]:
    """Pool measurements."""
    return load_json_array_fixture("last_measures.json", DOMAIN)


@pytest.fixture(scope="session")
def two_pools(
    pool1: list[dict[str, Any]], pool2: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Two pools description."""
    return [*pool1, *pool2]
