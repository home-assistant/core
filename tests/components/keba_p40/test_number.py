"""Tests for the KEBA P40 current-limit number."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

from keba_kecontact_p40 import KebaP40Error, Wallbox
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.keba_p40.const import DOMAIN
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_load_fixture, snapshot_platform


@pytest.mark.usefixtures("mock_client", "entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the current-limit number via snapshot."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_sets_current(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the current limit calls set_max_current in mA."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.garage_charging_current_limit", ATTR_VALUE: 10},
        blocking=True,
    )
    mock_client.set_max_current.assert_called_once_with(10000)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a set_max_current error raises HomeAssistantError."""
    mock_client.set_max_current.side_effect = KebaP40Error
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.garage_charging_current_limit", ATTR_VALUE: 10},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_native_value_none_without_meter(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test native_value returns None when wallbox has no meter data."""
    data: dict[str, Any] = json.loads(
        await async_load_fixture(hass, "wallbox.json", DOMAIN)
    )
    data["meter"] = None
    wallbox_no_meter = Wallbox.from_api(data)
    mock_client.get_wallbox.return_value = wallbox_no_meter
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.garage_charging_current_limit")
    assert state is not None
    assert state.state == "unknown"
