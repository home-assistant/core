"""Configuration for Flexit Nordic (BACnet) tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from flexit_bacnet import FlexitBACnet
import pytest

from homeassistant import config_entries
from homeassistant.components.flexit_bacnet.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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
    flexit_bacnet = AsyncMock(spec=FlexitBACnet)
    with patch(
        "homeassistant.components.flexit_bacnet.config_flow.FlexitBACnet",
        return_value=flexit_bacnet,
    ), patch(
        "homeassistant.components.flexit_bacnet.coordinator.FlexitBACnet",
        return_value=flexit_bacnet,
    ):
        flexit_bacnet.serial_number = "0000-0001"
        flexit_bacnet.device_name = "Device Name"
        flexit_bacnet.room_temperature = 19.0
        flexit_bacnet.air_temp_setpoint_away = 18.0
        flexit_bacnet.air_temp_setpoint_home = 22.0
        flexit_bacnet.ventilation_mode = 4

        yield flexit_bacnet


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.flexit_bacnet.async_setup_entry", return_value=True
    ) as setup_entry_mock:
        yield setup_entry_mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_DEVICE_ID: 2,
        },
        unique_id="0000-0001",
    )
