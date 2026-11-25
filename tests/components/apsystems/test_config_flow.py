"""Test the APsystems Local API config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.apsystems.const import (
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_LAKE6,
    DOMAIN,
)
from homeassistant.components.apsystems.lake6.client import Lake6ApiError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import LAKE6_DEV_ID, LAKE6_IP


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_create_success(
    hass: HomeAssistant, mock_apsystems: AsyncMock
) -> None:
    """Test we handle creatinw with success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    assert result["result"].unique_id == "MY_SERIAL_NUMBER"
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["data"].get(CONF_IP_ADDRESS) == "127.0.0.1"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_create_success_custom_port(
    hass: HomeAssistant, mock_apsystems: AsyncMock
) -> None:
    """Test we handle creating with custom port with success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: 8042,
        },
    )
    assert result["result"].unique_id == "MY_SERIAL_NUMBER"
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["data"].get(CONF_IP_ADDRESS) == "127.0.0.1"
    assert result["data"].get(CONF_PORT) == 8042


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect_and_recover(
    hass: HomeAssistant, mock_apsystems: AsyncMock
) -> None:
    """Test we handle cannot connect error."""

    mock_apsystems.get_device_info.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "127.0.0.2",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_apsystems.get_device_info.side_effect = None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    assert result2["result"].unique_id == "MY_SERIAL_NUMBER"
    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2["data"].get(CONF_IP_ADDRESS) == "127.0.0.1"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect_and_recover_custom_port(
    hass: HomeAssistant, mock_apsystems: AsyncMock
) -> None:
    """Test we handle cannot connect error but recovering with custom port."""

    mock_apsystems.get_device_info.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_IP_ADDRESS: "127.0.0.2", CONF_PORT: 8042},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_apsystems.get_device_info.side_effect = None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_IP_ADDRESS: "127.0.0.1", CONF_PORT: 8042},
    )
    assert result2["result"].unique_id == "MY_SERIAL_NUMBER"
    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2["data"].get(CONF_IP_ADDRESS) == "127.0.0.1"
    assert result2["data"].get(CONF_PORT) == 8042


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_unique_id_already_configured(
    hass: HomeAssistant, mock_apsystems: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle cannot connect error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "127.0.0.2",
        },
    )
    assert result["reason"] == "already_configured"
    assert result.get("type") is FlowResultType.ABORT


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_create_lake6(
    hass: HomeAssistant, mock_lake6_config_flow: MagicMock
) -> None:
    """Test a Lake_6 unit is identified by the model it reports."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: DEVICE_TYPE_LAKE6,
            CONF_IP_ADDRESS: LAKE6_IP,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ema"
    assert result["result"].unique_id == LAKE6_DEV_ID
    assert result["data"][CONF_DEVICE_TYPE] == DEVICE_TYPE_LAKE6


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_lake6_cannot_connect(
    hass: HomeAssistant, mock_lake6_config_flow: MagicMock
) -> None:
    """Test an unreachable Lake_6 unit reports cannot_connect."""
    mock_lake6_config_flow.return_value.async_get_device.side_effect = Lake6ApiError(
        "unreachable"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: DEVICE_TYPE_LAKE6,
            CONF_IP_ADDRESS: LAKE6_IP,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_lake6_config_flow.return_value.async_get_device.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: DEVICE_TYPE_LAKE6,
            CONF_IP_ADDRESS: LAKE6_IP,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == LAKE6_DEV_ID
