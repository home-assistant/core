"""Test the Theben Conexa Smartmeter gateway config flow."""

from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

import aiohttp
import pytest
from theben_conexa_smgw import ConexaSMGW

from homeassistant import config_entries
from homeassistant.components.theben_conexa.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_CONFIG_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


def _assert_create_entry_result(
    result: config_entries.ConfigFlowResult,
    expected_data: dict[str, str],
    mock_conexa_client: ConexaSMGW,
) -> None:
    """Assert a successful create-entry result uses the expected unique ID."""
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Smartmeter Gateway"
    assert result["data"] == expected_data
    assert result["result"].unique_id == (
        f"{mock_conexa_client.gatewayInfo.smgwID}-{expected_data[CONF_USERNAME]}"
    )


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_conexa_smgw: SimpleNamespace,
) -> None:
    """Test full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG_DATA,
    )

    _assert_create_entry_result(
        result,
        TEST_CONFIG_DATA,
        mock_conexa_smgw.client,
    )
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(aiohttp.ClientError, "invalid_auth", id="invalid-auth"),
        pytest.param(ValueError, "unknown", id="unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_conexa_smgw: SimpleNamespace,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test we handle exceptions from client creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_conexa_smgw.network.side_effect = None
    mock_conexa_smgw.create.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_conexa_smgw.create.side_effect = None
    mock_conexa_smgw.create.return_value = mock_conexa_smgw.client

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG_DATA,
    )

    _assert_create_entry_result(
        result,
        TEST_CONFIG_DATA,
        mock_conexa_smgw.client,
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_conexa_smgw: SimpleNamespace,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_conexa_smgw.network.side_effect = aiohttp.ClientError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_conexa_smgw.network.side_effect = None

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG_DATA,
    )

    _assert_create_entry_result(
        result,
        TEST_CONFIG_DATA,
        mock_conexa_smgw.client,
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if integration aborts if the user tries to configure an already configured smgw."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_same_gateway_different_user(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_conexa_smgw: SimpleNamespace,
) -> None:
    """Test that same gateway with a different username can still be configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG_DATA,
    )

    _assert_create_entry_result(
        result,
        TEST_CONFIG_DATA,
        mock_conexa_smgw.client,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username-2",
            CONF_PASSWORD: "test-password2",
        },
    )

    _assert_create_entry_result(
        result,
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username-2",
            CONF_PASSWORD: "test-password2",
        },
        mock_conexa_smgw.client,
    )
    assert len(mock_setup_entry.mock_calls) == 2


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication updates the password."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "name": mock_config_entry.title,
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        **TEST_CONFIG_DATA,
        CONF_PASSWORD: "new-password",
    }
    mock_conexa_smgw.create.assert_called_with(
        ANY, "1.1.1.1", "test-username", "new-password"
    )


@pytest.mark.parametrize(
    ("network_side_effect", "create_side_effect", "expected_error"),
    [
        pytest.param(aiohttp.ClientError, None, "cannot_connect", id="cannot-connect"),
        pytest.param(None, aiohttp.ClientError, "invalid_auth", id="invalid-auth"),
        pytest.param(None, ValueError, "unknown", id="unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
    network_side_effect: type[Exception] | None,
    create_side_effect: type[Exception] | None,
    expected_error: str,
) -> None:
    """Test reauthentication errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_conexa_smgw.network.side_effect = network_side_effect
    mock_conexa_smgw.create.side_effect = create_side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}

    mock_conexa_smgw.network.side_effect = None
    mock_conexa_smgw.create.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


async def test_reauth_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication aborts when the host now points to another gateway."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_conexa_smgw.client.gatewayInfo.smgwID = "other-gateway-id"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == TEST_CONFIG_DATA
