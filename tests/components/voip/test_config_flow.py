"""Test VoIP config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import voip
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_user(hass: HomeAssistant) -> None:
    """Test user form config flow."""

    result = await hass.config_entries.flow.async_init(
        voip.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert not result["errors"]

    with patch(
        "homeassistant.components.voip.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_instance(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> None:
    """Test that only one instance can be created."""
    result = await hass.config_entries.flow.async_init(
        voip.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=voip.DOMAIN,
        data={},
        unique_id="1234",
    )
    config_entry.add_to_hass(hass)

    assert config_entry.options == {}

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    # Default
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options == {"sip_port": 5060}

    # Manual
    result = await hass.config_entries.options.async_init(
        config_entry.entry_id,
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"sip_port": 5061},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options == {"sip_port": 5061}
