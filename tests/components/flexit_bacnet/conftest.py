"""Configuration for Flexit Nordic (BACnet) tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.flexit_bacnet.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
async def flow_id(hass: HomeAssistant) -> str:
    """Return initial ID for user-initiated configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    return result["flow_id"]


@pytest.fixture
def mock_flexit_bacnet() -> Generator[AsyncMock, None, None]:
    """Mock data from the device."""
    with patch(
        "homeassistant.components.flexit_bacnet.config_flow.FlexitBACnet",
        autospec=True,
    ) as flexit_bacnet_mock:
        flexit_bacnet = flexit_bacnet_mock.return_value
        flexit_bacnet.serial_number = "0000-0001"
        flexit_bacnet.device_name = "Device Name"
        flexit_bacnet.update.return_value = None

        yield flexit_bacnet


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.flexit_bacnet.async_setup_entry", return_value=True
    ) as setup_entry_mock:
        yield setup_entry_mock
