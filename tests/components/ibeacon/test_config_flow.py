"""Test the ibeacon config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.ibeacon.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_setup_user_no_bluetooth(
    hass: HomeAssistant, mock_bluetooth_adapters: None
) -> None:
    """Test setting up via user interaction when bluetooth is not enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "bluetooth_not_available"


async def test_setup_user(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test setting up via user interaction with bluetooth enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch("homeassistant.components.ibeacon.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "iBeacon Tracker"
    assert result2["data"] == {}


async def test_setup_user_already_setup(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test setting up via user when already setup ."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
