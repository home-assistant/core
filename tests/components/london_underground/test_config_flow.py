"""Test the London Underground config flow."""

import asyncio
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.london_underground.const import (
    CONF_LINE,
    DEFAULT_LINES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.london_underground.config_flow.validate_input",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "London Underground"
    assert result2["data"] == {}
    assert result2["options"] == {CONF_LINE: DEFAULT_LINES}


async def test_options(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_LINE: DEFAULT_LINES},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_LINE: ["Bakerloo", "Central"],
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_LINE: ["Bakerloo", "Central"],
    }


async def test_validate_input_connection_error(hass: HomeAssistant) -> None:
    """Test validation with connection error."""
    with patch(
        "homeassistant.components.london_underground.config_flow.TubeData"
    ) as mock_tube_data:
        mock_tube_data_instance = mock_tube_data.return_value
        mock_tube_data_instance.update.side_effect = Exception

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.london_underground.config_flow.async_get_clientsession",
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_LINE: ["Bakerloo", "Central"]},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"

    # confirm that we can recover from the error
    with patch(
        "homeassistant.components.london_underground.config_flow.validate_input",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "London Underground"
    assert result3["data"] == {}
    assert result3["options"] == {CONF_LINE: DEFAULT_LINES}


async def test_validate_input_timeout(hass: HomeAssistant) -> None:
    """Test validate_input times out."""
    with patch(
        "homeassistant.components.london_underground.config_flow.TubeData"
    ) as mock_tube_data:
        mock_tube_data_instance = mock_tube_data.return_value
        mock_tube_data_instance.update.side_effect = asyncio.TimeoutError

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.london_underground.config_flow.async_get_clientsession",
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_LINE: ["Bakerloo", "Central"]},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"

    # confirm that we can recover from the error
    with patch(
        "homeassistant.components.london_underground.config_flow.validate_input",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "London Underground"
    assert result3["data"] == {}
    assert result3["options"] == {CONF_LINE: DEFAULT_LINES}


async def test_validate_input_success(hass: HomeAssistant) -> None:
    """Test successful validation of TfL API."""
    with patch(
        "homeassistant.components.london_underground.config_flow.TubeData"
    ) as mock_tube_data:
        mock_tube_data_instance = mock_tube_data.return_value
        mock_tube_data_instance.update = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LINE: ["Bakerloo", "Central"]},
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "London Underground"
        assert result2["data"] == {}
        assert result2["options"] == {CONF_LINE: ["Bakerloo", "Central"]}
