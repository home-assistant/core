"""Tests for the Hot Spring config flow."""

from unittest.mock import MagicMock

from hotspring import HotSpringConnectionError, HotSpringError, Spa
import pytest

from homeassistant.components.hotspring.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, get_schema_suggested_value


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

    assert result["title"] == "ConnectedSpa_DDEEFF"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


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
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"


@pytest.mark.parametrize(
    "exception",
    [HotSpringConnectionError, HotSpringError],
)
@pytest.mark.usefixtures("mock_setup_entry")
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

    assert result["title"] == "ConnectedSpa_DDEEFF"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_no_mac_address(
    hass: HomeAssistant, mock_hotspring: MagicMock, device_fixture: Spa
) -> None:
    """Test we show user form on missing MAC address and recover."""
    device_fixture.info.root_topic = "unknownTopic123"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    device_fixture.info.root_topic = "mySpaAABBCCDDEEFF"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result["title"] == "ConnectedSpa_DDEEFF"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test the full reconfigure flow from start to finish."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"] is not None
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == "192.168.1.100"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"


async def test_full_reconfigure_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test reconfiguration failure when the unique ID changes."""
    mock_config_entry.add_to_hass(hass)
    device_fixture.info.root_topic = "mySpa112233445566"

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_reconfigure_flow_connection_error_and_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test reconfigure flow with connection error and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"] is not None
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == "192.168.1.100"
    )

    mock_hotspring.update.side_effect = HotSpringConnectionError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["data_schema"] is not None
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == "192.168.1.200"
    )

    mock_hotspring.update.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
