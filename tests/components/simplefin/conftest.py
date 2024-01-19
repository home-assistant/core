"""Test fixtures for SimpleFIN."""
from unittest.mock import patch

import pytest
from simplefin4py import FinancialData

from tests.common import load_fixture


@pytest.fixture
def mock_get_financial_data() -> FinancialData:
    """Fixture to mock the fetch_data method of SimpleFin."""
    fixture_data = load_fixture("simplefin/user_data_1.json")
    fin_data = FinancialData(**fixture_data)
    with patch(
        "homeassistant.components.simplefin.coordinator.SimpleFin.fetch_data",
    ) as mock_fetch_data:
        mock_fetch_data.return_value = fin_data
        yield


@pytest.fixture
def mock_claim_setup_token() -> str:
    """Fixture to mock the claim_setup_token method of SimpleFin."""
    with patch(
        "homeassistant.components.simplefin.config_flow.SimpleFin.claim_setup_token",
    ) as mock_claim_setup_token:
        mock_claim_setup_token.return_value = "https://i:am@yomama.comma"
        yield
