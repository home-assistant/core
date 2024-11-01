"""Test the Google Translate text-to-speech config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.google_translate.const import CONF_TLD, DOMAIN
from homeassistant.components.tts import CONF_LANG
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_step(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test user step create entry result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LANG: "de",
            CONF_TLD: "de",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Translate text-to-speech"
    assert result["data"] == {
        CONF_LANG: "de",
        CONF_TLD: "de",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user step already configured entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_LANG: "de", CONF_TLD: "de"}
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LANG: "de",
            CONF_TLD: "de",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_onboarding_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the onboarding configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "onboarding"}
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Google Translate text-to-speech"
    assert result.get("data") == {
        CONF_LANG: "en",
        CONF_TLD: "com",
    }

    assert len(mock_setup_entry.mock_calls) == 1
