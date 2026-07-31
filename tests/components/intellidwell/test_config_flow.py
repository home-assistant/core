"""Test the IntelliDwell Sprinkler Controller config flow."""

from unittest.mock import patch

from pyintellidwell import IntelliDwellConnectionError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.intellidwell.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_flow_user_init(hass: HomeAssistant) -> None:
    """Test user setup flow initiates correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_flow_user_success(hass: HomeAssistant) -> None:
    """Test successful configuration setup flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.intellidwell.config_flow.IntelliDwellClient.get_status",
            return_value={"relay_states": [0] * 10},
        ),
        patch(
            "homeassistant.components.intellidwell.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "IntelliDwell Sprinkler (1.1.1.1)"
    assert result2["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection error handling during configuration, then recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.intellidwell.config_flow.IntelliDwellClient.get_status",
        side_effect=IntelliDwellConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.intellidwell.config_flow.IntelliDwellClient.get_status",
            return_value={"relay_states": [0] * 10},
        ),
        patch(
            "homeassistant.components.intellidwell.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["title"] == "IntelliDwell Sprinkler (1.1.1.1)"
    assert result3["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_user_duplicate(hass: HomeAssistant) -> None:
    """Test duplicate host setup aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        entry_id="mock_entry",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_flow_user_unknown_error(hass: HomeAssistant) -> None:
    """Test unexpected exception handling during configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.intellidwell.config_flow.IntelliDwellClient.get_status",
        side_effect=Exception("Generic error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
