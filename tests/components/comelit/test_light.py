"""Tests for Comelit SimpleHome light platform."""

from unittest.mock import AsyncMock, patch

from aiocomelit.api import ComelitSerialBridgeObject
from aiocomelit.const import LIGHT, WATT
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.comelit.const import SCAN_INTERVAL
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "light.light0"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.comelit.BRIDGE_PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_serial_bridge_config_entry)

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_serial_bridge_config_entry.entry_id,
    )


@pytest.mark.parametrize(
    ("service", "status"),
    [
        (SERVICE_TURN_OFF, STATE_OFF),
        (SERVICE_TURN_ON, STATE_ON),
        (SERVICE_TOGGLE, STATE_ON),
    ],
)
async def test_light_set_state(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    service: str,
    status: str,
) -> None:
    """Test light set state service."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF

    # Test set temperature
    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == status


async def test_light_dynamic(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test light dynamically added."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert hass.states.get(ENTITY_ID)

    entity_id_2 = "light.light1"

    mock_serial_bridge.get_all_devices.return_value[LIGHT] = {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Light0",
            status=0,
            human_status="stopped",
            type="light",
            val=0,
            protected=0,
            zone="Open space",
            power=0.0,
            power_unit=WATT,
        ),
        1: ComelitSerialBridgeObject(
            index=1,
            name="Light1",
            status=0,
            human_status="stopped",
            type="light",
            val=0,
            protected=0,
            zone="Open space",
            power=0.0,
            power_unit=WATT,
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID)
    assert hass.states.get(entity_id_2)
