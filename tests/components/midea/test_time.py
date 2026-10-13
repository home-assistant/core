"""Tests for midea time.py."""

from collections.abc import Callable
from datetime import time
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ed import DeviceAttributes as EDAttributes
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


async def _assert_service_call(
    hass: HomeAssistant,
    entity_id: str,
    time: time,
    service: str,
    expected_calls: list[tuple],
    device: DummyDevice,
) -> None:
    """Call a switch service and assert the fake device recorded the right call."""
    device.calls.clear()
    await hass.services.async_call(
        TIME_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: time},
        blocking=True,
    )
    assert device.calls == expected_calls


@pytest.mark.parametrize(
    "device",
    [
        pytest.param(
            DummyDevice(
                DeviceType.ED,
                attributes={
                    EDAttributes.timing_regeneration_hour: 10,
                    EDAttributes.timing_regeneration_min: 14,
                },
            ),
            id="ed",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.ED,
                attributes={
                    EDAttributes.timing_regeneration_hour: 25,
                    EDAttributes.timing_regeneration_min: 45,
                },
            ),
            id="ed_invalid_hour",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.ED,
                attributes={
                    EDAttributes.timing_regeneration_hour: -3,
                    EDAttributes.timing_regeneration_min: 8,
                },
            ),
            id="ed_negative_hour",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.ED,
                attributes={
                    EDAttributes.timing_regeneration_hour: None,
                    EDAttributes.timing_regeneration_min: 53,
                },
            ),
            id="ed_none_hour",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.ED,
                attributes={
                    EDAttributes.timing_regeneration_hour: 13,
                    EDAttributes.timing_regeneration_min: 88,
                },
            ),
            id="ed_invalid_minute",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.ED,
                attributes={
                    EDAttributes.timing_regeneration_hour: 8,
                    EDAttributes.timing_regeneration_min: -12,
                },
            ),
            id="ed_negative_minute",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.ED,
                attributes={
                    EDAttributes.timing_regeneration_hour: 4,
                    EDAttributes.timing_regeneration_min: None,
                },
            ),
            id="ed_none_minute",
        ),
    ],
)
async def test_switch_state_snapshot(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device: DummyDevice,
) -> None:
    """Test async_setup_entry creates the right time entity."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, config_entry, device)

        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_ed_time_service(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test ED time service call reach the device."""
    device = DummyDevice(
        DeviceType.ED,
        attributes={
            EDAttributes.timing_regeneration_hour: 10,
            EDAttributes.timing_regeneration_min: 14,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[
        f"{TEST_DEVICE_ID}_timing_regeneration"
    ]

    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "10:14:00"

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        time(8, 56),
        SERVICE_SET_VALUE,
        [
            ("set_attribute", EDAttributes.timing_regeneration_hour, 8),
            ("set_attribute", EDAttributes.timing_regeneration_min, 56),
        ],
        device,
    )
