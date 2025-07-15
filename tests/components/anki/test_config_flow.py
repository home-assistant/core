"""Test the Anki config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.anki.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_title_default_host(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that the title doesn't contain the host if it is the default."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch("homeassistant.components.anki.coordinator.AnkiDataUpdateCoordinator.sync"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "ankiuser@gmail.com",
                CONF_PASSWORD: "password",
                CONF_HOST: DEFAULT_HOST,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ankiuser@gmail.com"
    assert result["data"] == {
        CONF_USERNAME: "ankiuser@gmail.com",
        CONF_PASSWORD: "password",
        CONF_HOST: DEFAULT_HOST,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_title_not_default_host(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that the title contains the host if it is not the default."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch("homeassistant.components.anki.coordinator.AnkiDataUpdateCoordinator.sync"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "ankiuser@gmail.com",
                CONF_PASSWORD: "password",
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ankiuser@gmail.com on 1.1.1.1"
    assert result["data"] == {
        CONF_USERNAME: "ankiuser@gmail.com",
        CONF_PASSWORD: "password",
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1
