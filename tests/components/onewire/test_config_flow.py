"""Tests for 1-Wire config flow."""
from unittest.mock import AsyncMock, patch

from pyownet import protocol
import pytest

from homeassistant.components.onewire.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture(autouse=True, name="mock_setup_entry")
def override_async_setup_entry() -> AsyncMock:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.onewire.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock):
    """Test user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    # Invalid server
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
        side_effect=protocol.ConnError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

    # Valid server
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "1.2.3.4"
        assert result["data"] == {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1234,
        }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_duplicate(
    hass: HomeAssistant, config_entry: ConfigEntry, mock_setup_entry: AsyncMock
):
    """Test user duplicate flow."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Duplicate server
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
