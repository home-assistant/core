"""Tests for the Pinecil config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.iron_os import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEFAULT_NAME, PINECIL_SERVICE_INFO, USER_INPUT

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("discovery")
async def test_async_step_user(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("discovery")
async def test_async_step_user_device_added_between_steps(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the device gets added via another flow between steps."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_no_device_discovered(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test setup with no device discoveries."""
    discovery.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=PINECIL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == "c0:ff:ee:c0:ff:ee"


async def test_async_step_bluetooth_devices_already_setup(
    hass: HomeAssistant, config_entry: AsyncMock
) -> None:
    """Test we can't start a flow if there is already a config entry."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=PINECIL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
