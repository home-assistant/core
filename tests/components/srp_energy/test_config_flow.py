"""Test the SRP Energy config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.srp_energy.const import CONF_IS_TOU, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_SOURCE, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    ACCNT_ID,
    ACCNT_ID_2,
    ACCNT_IS_TOU,
    ACCNT_NAME,
    ACCNT_NAME_2,
    ACCNT_PASSWORD,
    ACCNT_USERNAME,
    TEST_CONFIG_CABIN,
    TEST_CONFIG_HOME,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_srp_energy_config_flow")
async def test_show_form(
    hass: HomeAssistant, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.srp_energy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=TEST_CONFIG_HOME
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == ACCNT_NAME

        assert "data" in result
        assert result["data"][CONF_ID] == ACCNT_ID
        assert result["data"][CONF_USERNAME] == ACCNT_USERNAME
        assert result["data"][CONF_PASSWORD] == ACCNT_PASSWORD
        assert result["data"][CONF_IS_TOU] == ACCNT_IS_TOU

        captured = capsys.readouterr()
        assert "myaccount.srpnet.com" not in captured.err

        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_account(
    hass: HomeAssistant,
    mock_srp_energy_config_flow: MagicMock,
) -> None:
    """Test flow to handle invalid account error."""
    mock_srp_energy_config_flow.validate.side_effect = ValueError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=TEST_CONFIG_HOME
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_account"}


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_srp_energy_config_flow: MagicMock,
) -> None:
    """Test flow to handle invalid authentication error."""
    mock_srp_energy_config_flow.validate.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=TEST_CONFIG_HOME
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(
    hass: HomeAssistant,
    mock_srp_energy_config_flow: MagicMock,
) -> None:
    """Test flow to handle invalid authentication error."""
    mock_srp_energy_config_flow.validate.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=TEST_CONFIG_HOME
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_flow_entry_already_configured(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test user input for config_entry that already exists."""
    # Verify mock config setup from fixture
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.data[CONF_ID] == ACCNT_ID
    assert init_integration.unique_id == ACCNT_ID

    # Attempt a second config using same account id. This is the unique id between configs.
    user_input_second = TEST_CONFIG_HOME
    user_input_second[CONF_ID] = init_integration.data[CONF_ID]

    assert user_input_second[CONF_ID] == ACCNT_ID

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=user_input_second
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_multiple_configs(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test multiple config entries."""
    # Verify mock config setup from fixture
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.data[CONF_ID] == ACCNT_ID
    assert init_integration.unique_id == ACCNT_ID

    # Attempt a second config using different account id. This is the unique id between configs.
    assert TEST_CONFIG_CABIN[CONF_ID] != ACCNT_ID

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=TEST_CONFIG_CABIN
    )

    # Verify created
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCNT_NAME_2

    assert "data" in result
    assert result["data"][CONF_ID] == ACCNT_ID_2
    assert result["data"][CONF_USERNAME] == ACCNT_USERNAME
    assert result["data"][CONF_PASSWORD] == ACCNT_PASSWORD
    assert result["data"][CONF_IS_TOU] == ACCNT_IS_TOU

    # Verify multiple configs
    entries = hass.config_entries.async_entries()
    domain_entries = [entry for entry in entries if entry.domain == DOMAIN]
    assert len(domain_entries) == 2
