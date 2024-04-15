"""Test the Kuler Sky config flow."""

from unittest.mock import MagicMock, patch

import pykulersky

from homeassistant import config_entries
from homeassistant.components.kulersky.config_flow import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_flow_success(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    light = MagicMock(spec=pykulersky.Light)
    light.address = "AA:BB:CC:11:22:33"
    light.name = "Bedroom"
    with (
        patch(
            "homeassistant.components.kulersky.config_flow.pykulersky.discover",
            return_value=[light],
        ),
        patch(
            "homeassistant.components.kulersky.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Kuler Sky"
    assert result2["data"] == {}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_no_devices_found(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.kulersky.config_flow.pykulersky.discover",
            return_value=[],
        ),
        patch(
            "homeassistant.components.kulersky.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_flow_exceptions_caught(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.kulersky.config_flow.pykulersky.discover",
            side_effect=pykulersky.PykulerskyException("TEST"),
        ),
        patch(
            "homeassistant.components.kulersky.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"
    assert len(mock_setup_entry.mock_calls) == 0
