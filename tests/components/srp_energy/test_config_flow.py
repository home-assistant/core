"""Test the SRP Energy config flow."""
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.components.srp_energy import CONF_IS_TOU, DOMAIN
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_SOURCE, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ACCNT_ID, ACCNT_IS_TOU, ACCNT_PASSWORD, ACCNT_USERNAME, TEST_USER_INPUT

from tests.common import MockConfigEntry


async def test_show_form(hass, mock_srp_energy_config_flow: MagicMock, capsys) -> None:
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=TEST_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test home"

    assert "data" in result
    assert result["data"][CONF_ID] == ACCNT_ID
    assert result["data"][CONF_USERNAME] == ACCNT_USERNAME
    assert result["data"][CONF_PASSWORD] == ACCNT_PASSWORD
    assert result["data"][CONF_IS_TOU] == ACCNT_IS_TOU

    assert "result" in result
    assert result["result"].unique_id == ACCNT_ID

    captured = capsys.readouterr()
    assert "myaccount.srpnet.com" not in captured.err


async def test_form_invalid_account(
    hass: HomeAssistant,
    mock_srp_energy_config_flow: MagicMock,
) -> None:
    """Test flow to handle invalid account error."""
    mock_srp_energy_config_flow.validate.side_effect = ValueError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_account"}


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_srp_energy_config_flow: MagicMock,
) -> None:
    """Test flow to handle invalid authentication error."""
    mock_srp_energy_config_flow.validate.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(
    hass: HomeAssistant,
    mock_srp_energy_config_flow: MagicMock,
) -> None:
    """Test flow to handle invalid authentication error."""
    mock_srp_energy_config_flow.validate.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_flow_entry_already_configured(
    hass, init_integration: MockConfigEntry
) -> None:
    """Test user input for config_entry that already exists."""
    user_input = {
        CONF_ID: init_integration.data[CONF_ID],
        CONF_USERNAME: "abba2",
        CONF_PASSWORD: "ana2",
        CONF_IS_TOU: False,
    }

    assert user_input[CONF_ID] == ACCNT_ID

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}, data=user_input
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_two_entries(
    hass,
    mock_srp_energy,
    mock_srp_energy_config_flow,
) -> None:
    """Test configuring two entries."""

    user_input_one = {
        CONF_ID: "123456789",
        CONF_USERNAME: "abba2",
        CONF_PASSWORD: "ana2",
        CONF_IS_TOU: False,
    }

    user_input_two = {
        CONF_ID: "987654321",
        CONF_USERNAME: "2abba",
        CONF_PASSWORD: "2ana",
        CONF_IS_TOU: True,
    }

    for user_input in [user_input_one, user_input_two]:

        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=user_input,
            unique_id=user_input[CONF_ID],
        )

        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    domain_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(domain_entries) == 2
