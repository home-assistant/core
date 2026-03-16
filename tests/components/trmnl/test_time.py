"""Tests for the TRMNL time platform."""

from datetime import time, timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from trmnl.exceptions import TRMNLError
from trmnl.models import Device

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
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
    """Test all time entities."""
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "new_value", "expected_kwargs"),
    [
        (
            "time.test_trmnl_sleep_start_time",
            time(22, 0),
            {"sleep_start_time": 1320},
        ),
        (
            "time.test_trmnl_sleep_end_time",
            time(8, 0),
            {"sleep_end_time": 480},
        ),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    new_value: time,
    expected_kwargs: dict[str, int],
) -> None:
    """Test setting a time value calls the client and triggers a coordinator refresh."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: new_value},
        blocking=True,
    )

    mock_trmnl_client.update_device.assert_called_once_with(42793, **expected_kwargs)
    assert mock_trmnl_client.get_devices.call_count == 2


async def test_action_error(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a TRMNLError during a time action raises HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    mock_trmnl_client.update_device.side_effect = TRMNLError("connection failed")

    with pytest.raises(HomeAssistantError, match="connection failed"):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "time.test_trmnl_sleep_start_time",
                ATTR_TIME: time(22, 0),
            },
            blocking=True,
        )


async def test_coordinator_unavailable(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that time entities become unavailable when the coordinator fails."""
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("time.test_trmnl_sleep_start_time").state != STATE_UNAVAILABLE
    )

    mock_trmnl_client.get_devices.side_effect = TRMNLError
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("time.test_trmnl_sleep_start_time").state == STATE_UNAVAILABLE
    )


async def test_dynamic_new_device(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new entities are added when a new device appears in coordinator data."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("time.test_trmnl_sleep_start_time") is not None
    assert hass.states.get("time.new_trmnl_sleep_start_time") is None

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

    assert hass.states.get("time.new_trmnl_sleep_start_time") is not None
