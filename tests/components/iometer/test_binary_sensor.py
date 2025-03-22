"""Test the IOmeter binary sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_iometer_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensors."""
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_bridge_connection_status"
        ).state
        == STATE_ON
    )

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_attachment_status"
        ).state
        == STATE_ON
    )

    mock_iometer_client.get_current_status.return_value.device.core.attachment_status = "detached"

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_attachment_status"
        ).state
        == STATE_OFF
    )

    mock_iometer_client.get_current_status.return_value.device.core.connection_status = "disconnected"
    mock_iometer_client.get_current_status.return_value.device.core.attachment_status = None

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_bridge_connection_status"
        ).state
        == STATE_OFF
    )
    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_attachment_status"
        ).state
        == STATE_UNKNOWN
    )
