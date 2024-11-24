"""Tests for the Stookwijzer config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stookwijzer.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_stookwijzer: MagicMock,
    mock_setup_entry: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 1.0, CONF_LONGITUDE: 1.1}},
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2 == snapshot

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_stookwijzer.async_transform_coordinates.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_connection_error(
    hass: HomeAssistant,
    mock_stookwijzer: MagicMock,
) -> None:
    """Test user configuration flow while connection fails."""
    original_return_value = mock_stookwijzer.async_transform_coordinates.return_value
    mock_stookwijzer.async_transform_coordinates.return_value = (None, None)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 1.0, CONF_LONGITUDE: 1.1}},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    # Ensure we can continue the flow, when it now works
    mock_stookwijzer.async_transform_coordinates.return_value = original_return_value

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: {CONF_LATITUDE: 1.0, CONF_LONGITUDE: 1.1}},
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
