"""Tests for the bosch_alarm config flow."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.bosch_alarm.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import setup_integration

from tests.common import MockConfigEntry


async def test_form_user(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_panel: AsyncMock,
    model_name: str,
    serial_number: str,
    config_flow_data: dict[str, Any],
) -> None:
    """Test the config flow for bosch_alarm."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config_flow_data,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Bosch {model_name}"
    assert (
        result["data"]
        == {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 7700,
            CONF_MODEL: model_name,
        }
        | config_flow_data
    )
    assert result["result"].unique_id == serial_number
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (asyncio.TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_panel: AsyncMock,
    config_flow_data: dict[str, Any],
    exception: Exception,
    message: str,
) -> None:
    """Test we handle exceptions correctly."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    mock_panel.connect.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": message}

    mock_panel.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config_flow_data,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (PermissionError, "invalid_auth"),
        (asyncio.TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_exceptions_user(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_panel: AsyncMock,
    config_flow_data: dict[str, Any],
    exception: Exception,
    message: str,
) -> None:
    """Test we handle exceptions correctly."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    mock_panel.connect.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], config_flow_data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": message}

    mock_panel.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], config_flow_data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("model", ["solution_3000", "amax_3000"])
async def test_entry_already_configured_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    config_flow_data: dict[str, Any],
) -> None:
    """Test if configuring an entity twice results in an error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "0.0.0.0"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("model", ["b5512"])
async def test_entry_already_configured_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    config_flow_data: dict[str, Any],
) -> None:
    """Test if configuring an entity twice results in an error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.1.1.1"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], config_flow_data
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_can_finish(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_panel: AsyncMock,
    model_name: str,
    serial_number: str,
    config_flow_data: dict[str, Any],
) -> None:
    """Test DHCP discovery flow can finish right away."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="test",
            ip="1.1.1.1",
            macaddress="34ea34b43b5a",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config_flow_data,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Bosch {model_name}"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_MAC: "34:ea:34:b4:3b:5a",
        CONF_PORT: 7700,
        CONF_MODEL: model_name,
        **config_flow_data,
    }


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (asyncio.exceptions.TimeoutError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_dhcp_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_panel: AsyncMock,
    model_name: str,
    serial_number: str,
    config_flow_data: dict[str, Any],
    exception: Exception,
    message: str,
) -> None:
    """Test DHCP discovery flow that fails to connect."""
    mock_panel.connect.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="test",
            ip="1.1.1.1",
            macaddress="34ea34b43b5a",
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == message


async def test_dhcp_updates_mac(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    model_name: str,
    serial_number: str,
    config_flow_data: dict[str, Any],
) -> None:
    """Test DHCP discovery flow that fails to connect."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="test",
            ip="0.0.0.0",
            macaddress="34ea34b43b5a",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_MAC] == "34:ea:34:b4:3b:5a"


@pytest.mark.parametrize("mac_address", ["34ea34b43b5a"])
async def test_dhcp_updates_host(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    mac_address: str | None,
    serial_number: str,
    config_flow_data: dict[str, Any],
) -> None:
    """Test DHCP updates host."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="test",
            ip="4.5.6.7",
            macaddress=mac_address,
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "4.5.6.7"


@pytest.mark.parametrize("model", ["solution_3000", "amax_3000"])
async def test_dhcp_abort_ongoing_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    config_flow_data: dict[str, Any],
) -> None:
    """Test if a dhcp flow is aborted if there is already an ongoing flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "0.0.0.0"}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="test",
            ip="0.0.0.0",
            macaddress="34ea34b43b5a",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    model_name: str,
    serial_number: str,
    config_flow_data: dict[str, Any],
) -> None:
    """Test reauth flow."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)

    config_flow_data = {k: f"{v}2" for k, v in config_flow_data.items()}

    assert result["step_id"] == "reauth_confirm"
    # Now check it works when there are no errors
    mock_panel.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=config_flow_data,
    )
    assert result["reason"] == "reauth_successful"
    compare = {**mock_config_entry.data, **config_flow_data}
    assert compare == mock_config_entry.data


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (OSError(), "cannot_connect"),
        (PermissionError(), "invalid_auth"),
        (Exception(), "unknown"),
    ],
)
async def test_reauth_flow_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    model_name: str,
    serial_number: str,
    config_flow_data: dict[str, Any],
    exception: Exception,
    message: str,
) -> None:
    """Test reauth flow."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)

    config_flow_data = {k: f"{v}2" for k, v in config_flow_data.items()}

    assert result["step_id"] == "reauth_confirm"
    mock_panel.connect.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=config_flow_data,
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == message
    mock_panel.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=config_flow_data,
    )
    assert result["reason"] == "reauth_successful"
    compare = {**mock_config_entry.data, **config_flow_data}
    assert compare == mock_config_entry.data


async def test_reconfig_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    model_name: str,
    serial_number: str,
    config_flow_data: dict[str, Any],
) -> None:
    """Test reconfig auth."""
    await setup_integration(hass, mock_config_entry)

    config_flow_data = {k: f"{v}2" for k, v in config_flow_data.items()}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config_flow_data,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 7700,
        CONF_MODEL: model_name,
        **config_flow_data,
    }


@pytest.mark.parametrize("model", ["b5512"])
async def test_reconfig_flow_incorrect_model(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    model_name: str,
    serial_number: str,
    config_flow_data: dict[str, Any],
) -> None:
    """Test reconfig fails with a different device."""
    await setup_integration(hass, mock_config_entry)

    config_flow_data = {k: f"{v}2" for k, v in config_flow_data.items()}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    mock_panel.model = "Solution 3000"

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "0.0.0.0", CONF_PORT: 7700},
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_mismatch"
