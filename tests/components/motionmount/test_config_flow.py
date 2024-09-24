"""Tests for the Vogel's MotionMount config flow."""

import dataclasses
import socket
from unittest.mock import MagicMock, PropertyMock

import motionmount
import pytest

from homeassistant.components.motionmount.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    HOST,
    MOCK_USER_INPUT,
    MOCK_ZEROCONF_TVM_SERVICE_INFO_V1,
    MOCK_ZEROCONF_TVM_SERVICE_INFO_V2,
    PORT,
    ZEROCONF_HOSTNAME,
    ZEROCONF_MAC,
    ZEROCONF_NAME,
)

from tests.common import MockConfigEntry

MAC = bytes.fromhex("c4dd57f8a55f")
pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


async def test_user_connection_error(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when there is an connection error."""
    mock_motionmount_config_flow.connect.side_effect = ConnectionRefusedError()

    user_input = MOCK_USER_INPUT.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_connection_error_invalid_hostname(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when an invalid hostname is provided."""
    mock_motionmount_config_flow.connect.side_effect = socket.gaierror()

    user_input = MOCK_USER_INPUT.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_timeout_error(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when there is a timeout error."""
    mock_motionmount_config_flow.connect.side_effect = TimeoutError()

    user_input = MOCK_USER_INPUT.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "time_out"


async def test_user_not_connected_error(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when there is a not connected error."""
    mock_motionmount_config_flow.connect.side_effect = motionmount.NotConnectedError()

    user_input = MOCK_USER_INPUT.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_connected"


async def test_user_response_error_single_device_old_ce_old_new_pro(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow creates an entry when there is a response error."""
    mock_motionmount_config_flow.connect.side_effect = (
        motionmount.MotionMountResponseError(motionmount.MotionMountResponse.NotFound)
    )

    user_input = MOCK_USER_INPUT.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT

    assert result["result"]


async def test_user_response_error_single_device_new_ce_old_pro(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow creates an entry when there is a response error."""
    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(
        return_value=b"\x00\x00\x00\x00\x00\x00"
    )

    user_input = MOCK_USER_INPUT.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ZEROCONF_NAME

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT

    assert result["result"]


async def test_user_response_error_single_device_new_ce_new_pro(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow creates an entry when there is a response error."""
    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)

    user_input = MOCK_USER_INPUT.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ZEROCONF_NAME

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT

    assert result["result"]
    assert result["result"].unique_id == ZEROCONF_MAC


async def test_user_response_error_multi_device_old_ce_old_new_pro(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when there are multiple devices."""
    mock_config_entry.add_to_hass(hass)

    mock_motionmount_config_flow.connect.side_effect = (
        motionmount.MotionMountResponseError(motionmount.MotionMountResponse.NotFound)
    )

    user_input = MOCK_USER_INPUT.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_response_error_multi_device_new_ce_new_pro(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when there are multiple devices."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)

    user_input = MOCK_USER_INPUT.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_connection_error(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when there is an connection error."""
    mock_motionmount_config_flow.connect.side_effect = ConnectionRefusedError()

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V1)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_connection_error_invalid_hostname(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when there is an connection error."""
    mock_motionmount_config_flow.connect.side_effect = socket.gaierror()

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V1)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_timout_error(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when there is a timeout error."""
    mock_motionmount_config_flow.connect.side_effect = TimeoutError()

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V1)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "time_out"


async def test_zeroconf_not_connected_error(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the flow is aborted when there is a not connected error."""
    mock_motionmount_config_flow.connect.side_effect = motionmount.NotConnectedError()

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V1)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_connected"


async def test_show_zeroconf_form_old_ce_old_pro(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the zeroconf confirmation form is served."""
    mock_motionmount_config_flow.connect.side_effect = (
        motionmount.MotionMountResponseError(motionmount.MotionMountResponse.NotFound)
    )

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V1)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_NAME: "My MotionMount"}


async def test_show_zeroconf_form_old_ce_new_pro(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the zeroconf confirmation form is served."""
    mock_motionmount_config_flow.connect.side_effect = (
        motionmount.MotionMountResponseError(motionmount.MotionMountResponse.NotFound)
    )

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V2)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_NAME: "My MotionMount"}


async def test_show_zeroconf_form_new_ce_old_pro(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the zeroconf confirmation form is served."""
    type(mock_motionmount_config_flow).mac = PropertyMock(
        return_value=b"\x00\x00\x00\x00\x00\x00"
    )

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V1)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_NAME: "My MotionMount"}


async def test_show_zeroconf_form_new_ce_new_pro(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test that the zeroconf confirmation form is served."""
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V2)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_NAME: "My MotionMount"}


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if device already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V2)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT.copy(),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ZEROCONF_NAME

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT

    assert result["result"]
    assert result["result"].unique_id == ZEROCONF_MAC


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)

    discovery_info = dataclasses.replace(MOCK_ZEROCONF_TVM_SERVICE_INFO_V2)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ZEROCONF_NAME

    assert result["data"]
    assert result["data"][CONF_HOST] == ZEROCONF_HOSTNAME
    assert result["data"][CONF_PORT] == PORT
    assert result["data"][CONF_NAME] == ZEROCONF_NAME

    assert result["result"]
    assert result["result"].unique_id == ZEROCONF_MAC
