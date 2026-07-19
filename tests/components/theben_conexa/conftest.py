"""Common fixtures for the Theben Conexa Smartmeter gateway tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.theben_conexa.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_conexa_smgw() -> Generator[MagicMock]:
    """Mock a shared ConexaSMGW client instance used by the integration."""
    mock_smgw = MagicMock()
    mock_smgw.gatewayInfo.smgwID = "test-gateway-id"

    with (
        patch(
            "homeassistant.components.theben_conexa.coordinator.checkNetworkConnection",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.theben_conexa.config_flow.checkNetworkConnection",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.theben_conexa.coordinator.ConexaSMGW.create",
            AsyncMock(return_value=mock_smgw),
        ),
        patch(
            "homeassistant.components.theben_conexa.config_flow.ConexaSMGW.create",
            AsyncMock(return_value=mock_smgw),
        ),
    ):
        yield mock_smgw
