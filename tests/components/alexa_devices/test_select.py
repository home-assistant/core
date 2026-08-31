"""Tests for the Alexa Devices select platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_DEVICE_1, TEST_DEVICE_1_SN

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "select.echo_test_drop_in"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_dropin_option(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a drop-in option."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "all"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "home"},
        blocking=True,
    )

    assert mock_amazon_devices_client.set_dropin_status.call_count == 1

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "home"

    device_data = deepcopy(TEST_DEVICE_1)
    device_data.communication_settings = {
        "announcements": "ON",
        "communications": "ON",
        "dropin": "Off",
    }
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: device_data
    }

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "off"},
        blocking=True,
    )

    assert mock_amazon_devices_client.set_dropin_status.call_count == 2
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "off"


async def test_offline_device(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test offline device handling."""
    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = False

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
