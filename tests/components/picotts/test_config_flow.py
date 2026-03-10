"""Test the Pico TTS config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import tts
from homeassistant.components.picotts.const import DOMAIN
from homeassistant.components.tts import CONF_LANG
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

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
            CONF_LANG: "es-ES",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pico TTS es-ES"
    assert result["data"] == {
        CONF_LANG: "es-ES",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user step already configured entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_LANG: "es-ES"})
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LANG: "es-ES",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_import_flow(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the import flow."""
    with patch("homeassistant.components.picotts.shutil.which", return_value="/usr/local/bin/pico2wave"):
        assert not hass.config_entries.async_entries(DOMAIN)
        assert await async_setup_component(
            hass,
            tts.DOMAIN,
            {tts.DOMAIN: {CONF_PLATFORM: DOMAIN}},
        )
        await hass.async_block_till_done()
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        config_entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert config_entry.state is config_entries.ConfigEntryState.LOADED
        assert issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_yaml_{DOMAIN}",
        )
