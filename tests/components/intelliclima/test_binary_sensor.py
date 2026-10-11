"""Test IntelliClima Binary Sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyintelliclima.intelliclima_types import (
    IntelliClimaDevices,
    IntelliClimaFilterStatus,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import async_poll, setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FAN_STATE_ENTITY_IDS = {
    "boost": "binary_sensor.test_vmc_boost",
    "night": "binary_sensor.test_vmc_night_mode",
    "advanced": "binary_sensor.test_vmc_advanced_control",
    "profiled": "binary_sensor.test_vmc_automatic_speed_control",
}


@pytest.fixture(autouse=True)
async def setup_intelliclima_binary_sensor_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the binary sensor platform."""
    with (
        patch(
            "homeassistant.components.intelliclima.PLATFORMS", [Platform.BINARY_SENSOR]
        ),
    ):
        await setup_integration(hass, mock_config_entry)
        yield


async def test_all_binary_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    binary_sensor_entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "intelliclima" and entry.domain == BINARY_SENSOR_DOMAIN
    ]
    assert len(binary_sensor_entries) == 5

    for entity_entry in binary_sensor_entries:
        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry == snapshot


async def test_filter_cleaning_unavailable_when_tracking_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test the filter_cleaning sensor is unavailable when the vendor disables filter tracking.

    The vendor API keeps returning `change_filter: false` in this state, which
    would otherwise misreport a "clean filter" the integration can't actually vouch for.
    """
    mock_cloud_interface.ecocomfort2.get_filter_status.return_value = (
        IntelliClimaFilterStatus(
            serial="11223344",
            is_active=False,
            from_date="2025-11-18 10:22:51",
            stats=[],
            totale=0,
            change_filter=False,
        )
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_vmc_filter_cleaning_required")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("mode_state", "speed_state", "flags_on"),
    [
        pytest.param("3", "2", set(), id="manual"),
        pytest.param("3", str(0x40 | 3), {"boost"}, id="boost"),
        pytest.param("2", str(0x80 | 3), {"night"}, id="night"),
        pytest.param("1", str(0x20 | 2), {"advanced"}, id="advanced"),
        pytest.param("4", str(0x10 | 2), {"profiled"}, id="auto"),
        pytest.param("4", "3", set(), id="sensor_manual_speed"),
    ],
)
async def test_fan_state_flags(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    single_eco_device: IntelliClimaDevices,
    mode_state: str,
    speed_state: str,
    flags_on: set[str],
) -> None:
    """Test each fan-state binary sensor follows its flag in the running state."""
    eco = single_eco_device.ecocomfort2_devices["56789"]
    eco.mode_state = mode_state
    eco.speed_state = speed_state
    await async_poll(hass, freezer)

    states = {
        flag: state.state
        for flag, entity_id in FAN_STATE_ENTITY_IDS.items()
        if (state := hass.states.get(entity_id))
    }
    assert states == {
        flag: STATE_ON if flag in flags_on else STATE_OFF
        for flag in FAN_STATE_ENTITY_IDS
    }


async def test_fan_state_flags_unknown_on_undefined_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    single_eco_device: IntelliClimaDevices,
) -> None:
    """Test the fan-state binary sensors are unknown when the running state is undefined."""
    single_eco_device.ecocomfort2_devices["56789"].mode_state = "7"
    await async_poll(hass, freezer)

    for entity_id in FAN_STATE_ENTITY_IDS.values():
        assert (state := hass.states.get(entity_id))
        assert state.state == STATE_UNKNOWN
