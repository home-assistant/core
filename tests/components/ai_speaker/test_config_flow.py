"""Test the AI Speaker config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.ai_speaker.config_flow import CannotConnect
from homeassistant.components.ai_speaker.const import DOMAIN

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.ai_speaker.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ai_speaker.async_setup_entry",
        return_value=True,
    ) as mock_gate_info, patch(
        "homeassistant.components.ai_speaker.config_flow.AisWebService.get_gate_info",
        return_value={"Product": "AIS DEV1", "ais_id": "dom-123"},
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "AI-Speaker AIS DEV1"
    assert result2["data"] == {"host": "1.1.1.1"}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_gate_info.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ai_speaker.config_flow.AisWebService.get_gate_info",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "abort"


async def test_form_timeout(hass):
    """Test we handle a connection timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ai_speaker.config_flow.AisWebService.get_gate_info",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_unexpected_exception(hass):
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ai_speaker.config_flow.AisWebService.get_gate_info",
        side_effect=ValueError("message"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_already_configured(hass):
    """Test that flow aborts when provided gate is already configured."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="dom-123",
        data={"host": "1.1.1.1"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ai_speaker.config_flow.AisWebService.get_gate_info",
        return_value={"Product": "AIS DEV1", "ais_id": "dom-123"},
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 1
