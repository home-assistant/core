"""Define tests for the ReCollect Waste config flow."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiorecollect.errors import RecollectError
import pytest

from homeassistant.components.recollect_waste.const import (
    CONF_PLACE_ID,
    CONF_SERVICE_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_PLACE_ID, TEST_SERVICE_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_aiorecollect")
async def test_create_entry(
    hass: HomeAssistant,
    client: Mock,
    config: dict[str, Any],
) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test errors that can arise when checking the API key:
    with patch.object(
        client, "async_get_pickup_events", AsyncMock(side_effect=RecollectError)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_place_or_service_id"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_PLACE_ID}, {TEST_SERVICE_ID}"
    assert result["data"] == {
        CONF_PLACE_ID: TEST_PLACE_ID,
        CONF_SERVICE_ID: TEST_SERVICE_ID,
    }


@pytest.mark.usefixtures("setup_config_entry")
async def test_duplicate_error(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("setup_config_entry")
async def test_options_flow(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test config flow options."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_FRIENDLY_NAME: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_FRIENDLY_NAME: True}
