"""Test the Starlink config flow."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.starlink.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {CONF_IP_ADDRESS: "192.168.100.1:9200"}


async def test_flow_user_fails_can_succeed(
    hass: HomeAssistant, mock_get_id: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Test user flow can succeed after failure when Starlink is available."""
    mock_get_id.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]

    mock_get_id.return_value = "some-valid-id"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


async def test_flow_user_success(
    hass: HomeAssistant, mock_get_id: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Test user initialized flow succeeds when Starlink is available."""
    mock_get_id.return_value = "some-valid-id"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "some-valid-id"


async def test_flow_user_duplicate_abort(
    hass: HomeAssistant, mock_get_id: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Test user initialized flow aborts when Starlink is already configured."""
    mock_get_id.return_value = "some-valid-id"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id="some-valid-id",
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
