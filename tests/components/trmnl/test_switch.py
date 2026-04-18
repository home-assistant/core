"""Tests for the TRMNL switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from trmnl.exceptions import TRMNLError
from trmnl.models import Device

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("mock_trmnl_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all switch entities."""
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "expected_value"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
async def test_set_switch(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_value: bool,
) -> None:
    """Test turning the sleep mode switch on and off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "switch",
        service,
        {ATTR_ENTITY_ID: "switch.test_trmnl_sleep_mode"},
        blocking=True,
    )

    mock_trmnl_client.update_device.assert_called_once_with(
        42793, sleep_mode_enabled=expected_value
    )
    assert mock_trmnl_client.get_devices.call_count == 2


@pytest.mark.parametrize(
    "service",
    [SERVICE_TURN_ON, SERVICE_TURN_OFF],
)
async def test_action_error(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test that a TRMNLError during a switch action raises HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    mock_trmnl_client.update_device.side_effect = TRMNLError("connection failed")

    with pytest.raises(HomeAssistantError, match="connection failed"):
        await hass.services.async_call(
            "switch",
            service,
            {ATTR_ENTITY_ID: "switch.test_trmnl_sleep_mode"},
            blocking=True,
        )


async def test_coordinator_unavailable(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that switch entities become unavailable when the coordinator fails."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_trmnl_sleep_mode").state != STATE_UNAVAILABLE

    mock_trmnl_client.get_devices.side_effect = TRMNLError
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_trmnl_sleep_mode").state == STATE_UNAVAILABLE


async def test_dynamic_new_device(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new entities are added when a new device appears in coordinator data."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_trmnl_sleep_mode") is not None
    assert hass.states.get("switch.new_trmnl_sleep_mode") is None

    new_device = Device(
        identifier=99999,
        name="New TRMNL",
        friendly_id="ABCDEF",
        mac_address="AA:BB:CC:DD:EE:FF",
        battery_voltage=4.0,
        rssi=-70,
        sleep_mode_enabled=False,
        sleep_start_time=0,
        sleep_end_time=0,
        percent_charged=85.0,
        wifi_strength=60,
    )
    mock_trmnl_client.get_devices.return_value = [
        *mock_trmnl_client.get_devices.return_value,
        new_device,
    ]
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.new_trmnl_sleep_mode") is not None
