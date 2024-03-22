"""Test the Amazon Bedrock Agent config flow."""

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry

CONST_DOMAIN = "bedrock_agent"


async def test_form(hass: HomeAssistant) -> None:
    """Test input form."""
    hass.config.components.add("bedrock_agent")
    MockConfigEntry(
        domain=CONST_DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        CONST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "key_id": "abc",
            "key_secret": "123",
            "region": "us-west-2",
            "model_id": "ai21.j2-mid-v1",
            "prompt_context": "123abc",
        },
    )

    assert result2["type"] == FlowResultType.FORM


async def test_invalid_model_id(hass: HomeAssistant) -> None:
    """Test unsupported model id."""
    hass.config.components.add("bedrock_agent")
    MockConfigEntry(
        domain=CONST_DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        CONST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "key_id": "abc",
                "key_secret": "123",
                "region": "us-west-2",
                "model_id": "123",
                "prompt_context": "123abc",
            },
        )


async def test_options_flow(hass: HomeAssistant, mock_config_entry) -> None:
    """Testing Options Flow."""
    options_flow = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    options = await hass.config_entries.options.async_configure(
        options_flow["flow_id"],
        {
            "key_id": "abc",
            "key_secret": "123",
            "region": "us-west-2",
            "model_id": "anthropic.claude-v2",
            "prompt_context": "123abc",
        },
    )
    assert options["type"] == FlowResultType.FORM


async def test_options_flow_invalid_model_id(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Testing Options Flow."""
    options_flow = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            options_flow["flow_id"],
            {
                "key_id": "abc",
                "key_secret": "123",
                "region": "us-west-2",
                "model_id": "123",
                "prompt_context": "123abc",
            },
        )


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, request):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="bedrock_agent",
        data={
            "region": "us-west-2",
            "key_id": "abc",
            "key_secret": "123",
            "model_id": "anthropic.claude-v2",
            "prompt_context": "test",
        },
    )
    entry.add_to_hass(hass)
    return entry
