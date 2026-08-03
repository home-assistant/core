"""Tests for the Hot Spring config flow."""

from unittest.mock import MagicMock

from hotspring import HotSpringConnectionError, HotSpringError
import pytest

from homeassistant.components.hotspring.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_hotspring")
async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["title"] == "ConnectedSpa_C59C9C"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"


@pytest.mark.usefixtures("mock_hotspring")
async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort the config flow if Hot Spring spa is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "exception",
    [HotSpringConnectionError, HotSpringError],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_hotspring")
async def test_form_cannot_connect(
    hass: HomeAssistant, mock_hotspring: MagicMock, exception: type[Exception]
) -> None:
    """Test we show user form on Hot Spring connection error and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    mock_hotspring.update.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_hotspring.update.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["title"] == "ConnectedSpa_C59C9C"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"
