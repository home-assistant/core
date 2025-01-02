"""Test the ViCare config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import dhcp
from homeassistant.components.vicare.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_MAC, MODULE

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

VALID_CONFIG = {
    CONF_USERNAME: "foo@bar.com",
    CONF_PASSWORD: "1234",
    CONF_CLIENT_ID: "5678",
}

DHCP_INFO = dhcp.DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="mock_hostname",
    macaddress=MOCK_MAC.lower().replace(":", ""),
)


async def test_user_create_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, snapshot: SnapshotAssertion
) -> None:
    """Test that the user step works."""
    # start user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # test PyViCareInvalidConfigurationError
    with patch(
        f"{MODULE}.config_flow.login",
        side_effect=PyViCareInvalidConfigurationError(
            {"error": "foo", "error_description": "bar"}
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    # test PyViCareInvalidCredentialsError
    with patch(
        f"{MODULE}.config_flow.login",
        side_effect=PyViCareInvalidCredentialsError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    # test success
    with patch(
        f"{MODULE}.config_flow.login",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ViCare"
    assert result["data"] == snapshot
    mock_setup_entry.assert_called_once()


async def test_step_reauth(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test reauth flow."""
    new_password = "ABCD"
    new_client_id = "EFGH"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # test PyViCareInvalidConfigurationError
    with patch(
        f"{MODULE}.config_flow.login",
        side_effect=PyViCareInvalidConfigurationError(
            {"error": "foo", "error_description": "bar"}
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: new_password, CONF_CLIENT_ID: new_client_id},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_auth"}

    # test success
    with patch(
        f"{MODULE}.config_flow.login",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: new_password, CONF_CLIENT_ID: new_client_id},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

        assert len(hass.config_entries.async_entries()) == 1
        assert (
            hass.config_entries.async_entries()[0].data[CONF_PASSWORD] == new_password
        )
        assert (
            hass.config_entries.async_entries()[0].data[CONF_CLIENT_ID] == new_client_id
        )
        await hass.async_block_till_done()


async def test_form_dhcp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, snapshot: SnapshotAssertion
) -> None:
    """Test we can setup from dhcp."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        f"{MODULE}.config_flow.login",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ViCare"
    assert result["data"] == snapshot
    mock_setup_entry.assert_called_once()


async def test_dhcp_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that configuring more than one instance is rejected."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_input_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that configuring more than one instance is rejected."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data=VALID_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
