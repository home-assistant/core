"""Test config flow for the TuneBlade Remote integration."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.tuneblade_remote.config_flow import TuneBladeConfigFlow
from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant, mock_tuneblade_api) -> None:
    """Test successful user-initiated config flow."""
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TestDevice"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 54412,
        "name": "TestDevice",
    }


@pytest.mark.asyncio
async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_tuneblade_api
) -> None:
    """Test user config flow with connection failure returning empty device list."""
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[])

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_flow_connection_exception(
    hass: HomeAssistant, mock_tuneblade_api
) -> None:
    """Test user config flow handles exception on connection attempt."""
    mock_tuneblade_api.async_get_data = AsyncMock(side_effect=Exception("fail"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"host": "127.0.0.1", "port": 54412, "name": "TestDevice"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_zeroconf_flow_success(hass: HomeAssistant, mock_tuneblade_api) -> None:
    """Test successful zeroconf discovery flow."""
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    discovery_info = SimpleNamespace(
        host="127.0.0.1",
        port=54412,
        name="TestDevice@local",
        type="_http._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TestDevice"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 54412,
        "name": "TestDevice",
    }


@pytest.mark.asyncio
async def test_zeroconf_flow_connection_exception(
    hass: HomeAssistant, mock_tuneblade_api
) -> None:
    """Test zeroconf discovery flow aborts on connection exception."""
    mock_tuneblade_api.async_get_data = AsyncMock(side_effect=Exception("fail"))

    discovery_info = SimpleNamespace(
        host="127.0.0.1",
        port=54412,
        name="TestDevice@local",
        type="_http._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.asyncio
async def test_zeroconf_flow_empty_devices_aborts(
    hass: HomeAssistant, mock_tuneblade_api
) -> None:
    """Test zeroconf discovery flow aborts if device list empty."""
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[])

    discovery_info = SimpleNamespace(
        host="127.0.0.1",
        port=54412,
        name="TestDevice@local",
        type="_http._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.asyncio
async def test_zeroconf_confirm_step_shows_form(
    hass: HomeAssistant, mock_tuneblade_api: Any
) -> None:
    """Test zeroconf confirm step shows form if no user input."""
    flow = TuneBladeConfigFlow()
    flow.hass = hass
    flow._discovery_info = {
        "host": "127.0.0.1",
        "port": 54412,
        "name": "TestDevice",
    }
    flow._title_placeholders = {"name": "TestDevice"}

    result = await flow.async_step_confirm(user_input=None)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert "description_placeholders" in result
    assert result["description_placeholders"]["name"] == "TestDevice"
    assert result["description_placeholders"]["ip"] == "127.0.0.1"


@pytest.mark.asyncio
async def test_user_flow_duplicate_unique_id_aborts(
    hass: HomeAssistant, mock_tuneblade_api
) -> None:
    """Test flow aborts if unique_id already configured."""
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TestDevice_127.0.0.1_54412",
        data={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
        title="TestDevice",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
