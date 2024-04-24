"""Test the zerproc config flow."""
from unittest.mock import patch

import pyzerproc

from homeassistant import config_entries
from homeassistant.components.zerproc.config_flow import DOMAIN
from homeassistant.core import HomeAssistant


async def test_flow_success(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.zerproc.config_flow.pyzerproc.discover",
        return_value=["Light1", "Light2"],
    ), patch(
        "homeassistant.components.zerproc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Zerproc"
    assert result2["data"] == {}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_no_devices_found(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.zerproc.config_flow.pyzerproc.discover",
        return_value=[],
    ), patch(
        "homeassistant.components.zerproc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 0


async def test_flow_exceptions_caught(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.zerproc.config_flow.pyzerproc.discover",
        side_effect=pyzerproc.ZerprocException("TEST"),
    ), patch(
        "homeassistant.components.zerproc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 0
