"""Test the HiFiBerry config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiohifiberry import AudioControlError

from homeassistant import config_entries
from homeassistant.components.hifiberry.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_CONNECTION = {CONF_HOST: "hifiberry.local", CONF_PORT: DEFAULT_PORT}


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "hifiberry.local"
    assert result2["data"] == TEST_CONNECTION
    assert result2["result"].unique_id is None
    mock_audiocontrol_client.async_validate.assert_awaited_once()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_audiocontrol_client: MagicMock
) -> None:
    """Test we handle connection errors."""
    mock_audiocontrol_client.async_validate.side_effect = AudioControlError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(
    hass: HomeAssistant, mock_audiocontrol_client: MagicMock
) -> None:
    """Test we handle unexpected errors."""
    mock_audiocontrol_client.async_validate.side_effect = RuntimeError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_duplicate_updates_existing_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test a duplicate host aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONNECTION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    mock_audiocontrol_client.async_validate.assert_awaited_once()
    assert len(mock_setup_entry.mock_calls) == 0
