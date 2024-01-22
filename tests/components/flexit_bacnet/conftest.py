"""Configuration for Flexit Nordic (BACnet) tests."""
from unittest.mock import patch

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


@pytest.fixture(autouse=True)
def mock_serial_number_and_device_name():
    """Mock serial number of the device."""
    with patch(
        "homeassistant.components.flexit_bacnet.config_flow.FlexitBACnet.serial_number",
        "0000-0001",
    ), patch(
        "homeassistant.components.flexit_bacnet.config_flow.FlexitBACnet.device_name",
        "Device Name",
    ):
        yield


@pytest.fixture
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.flexit_bacnet.async_setup_entry", return_value=True
    ) as setup_entry_mock:
        yield setup_entry_mock
