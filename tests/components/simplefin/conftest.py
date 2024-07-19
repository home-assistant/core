"""Test fixtures for SimpleFIN."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from simplefin4py import FinancialData
from simplefin4py.exceptions import SimpleFinInvalidClaimTokenError

from homeassistant.components.simplefin import CONF_ACCESS_URL
from homeassistant.components.simplefin.const import DOMAIN

from tests.common import MockConfigEntry, load_fixture

MOCK_ACCESS_URL = "https://i:am@yomama.house.com"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.simplefin.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def mock_config_entry() -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_URL: MOCK_ACCESS_URL},
        version=1,
    )


@pytest.fixture
def mock_claim_setup_token() -> str:
    """Fixture to mock the claim_setup_token method of SimpleFin."""
    with patch(
        "homeassistant.components.simplefin.config_flow.SimpleFin.claim_setup_token",
    ) as mock_claim_setup_token:
        mock_claim_setup_token.return_value = "https://i:am@yomama.comma"
        yield


@pytest.fixture
def mock_decode_claim_token_invalid_then_good() -> str:
    """Fixture to mock the decode_claim_token method of SimpleFin."""
    return_values = [SimpleFinInvalidClaimTokenError, "valid_return_value"]
    with patch(
        "homeassistant.components.simplefin.config_flow.SimpleFin.decode_claim_token",
        new_callable=lambda: MagicMock(side_effect=return_values),
    ):
        yield


@pytest.fixture
def mock_simplefin_client() -> Generator[AsyncMock]:
    """Mock a SimpleFin client."""

    with (
        patch(
            "homeassistant.components.simplefin.SimpleFin",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.simplefin.config_flow.SimpleFin",
            new=mock_client,
        ),
    ):
        mock_client.claim_setup_token.return_value = MOCK_ACCESS_URL
        client = mock_client.return_value

        fixture_data = load_fixture("fin_data.json", DOMAIN)
        fin_data = FinancialData.from_json(fixture_data)

        assert fin_data.accounts != []
        client.fetch_data.return_value = fin_data

        client.access_url = MOCK_ACCESS_URL

        yield mock_client
