"""Common fixtures for the Theben Conexa Smartmeter gateway tests."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.theben_conexa.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

TEST_CONFIG_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.theben_conexa.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_conexa_smgw() -> Generator[SimpleNamespace]:
    """Mock the Theben Conexa API surface used by the integration."""
    mock_network = AsyncMock(return_value=None)
    mock_create = AsyncMock()

    mock_smgw = MagicMock()
    mock_smgw.gatewayInfo.smgwID = "test-gateway-id"
    mock_smgw.gatewayInfo.firmwareVersion = "test-gateway-fw-version"
    mock_smgw.getLatestValues = AsyncMock(return_value={})
    mock_create.return_value = mock_smgw

    with (
        patch("theben_conexa_smgw.checkNetworkConnection", mock_network),
        patch(
            "homeassistant.components.theben_conexa.coordinator.checkNetworkConnection",
            mock_network,
        ),
        patch(
            "homeassistant.components.theben_conexa.config_flow.checkNetworkConnection",
            mock_network,
        ),
        patch("theben_conexa_smgw.ConexaSMGW.create", mock_create),
        patch(
            "homeassistant.components.theben_conexa.coordinator.ConexaSMGW.create",
            mock_create,
        ),
        patch(
            "homeassistant.components.theben_conexa.config_flow.ConexaSMGW.create",
            mock_create,
        ),
    ):
        yield SimpleNamespace(
            network=mock_network,
            create=mock_create,
            client=mock_smgw,
        )


@pytest.fixture
def mock_config_entry(mock_conexa_smgw: SimpleNamespace) -> MockConfigEntry:
    """Create a configured MockConfigEntry for the integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{mock_conexa_smgw.client.gatewayInfo.smgwID}-test-username",
        data=TEST_CONFIG_DATA,
    )
