"""Test IntelliClima Binary Sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyintelliclima.intelliclima_types import (
    IntelliClimaDevices,
    IntelliClimaFilterStatus,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_poll, setup_integration

FAN_STATE_ENTITY_IDS = {
    "boost": "binary_sensor.test_vmc_boost",
    "night": "binary_sensor.test_vmc_night_mode",
    "advanced": "binary_sensor.test_vmc_advanced_control",
    "profiled": "binary_sensor.test_vmc_automatic_speed_control",
}


@pytest.mark.parametrize(
    ("dev_state", "expected"),
    [
        pytest.param("0", STATE_OFF, id="clean"),
        pytest.param("1", STATE_ON, id="cleaning_due"),
        pytest.param(None, STATE_UNKNOWN, id="no_reading"),
    ],
)
async def test_eco3_filter_warning(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mixed_eco_devices: IntelliClimaDevices,
    mock_cloud_interface: AsyncMock,
    dev_state: str | None,
    expected: str,
) -> None:
    """Read ECO3's filter warning from dev_state without a filter API request."""
    mixed_eco_devices.ecocomfort3_devices["33333"].dev_state = dev_state
    await async_poll(hass, freezer)
    assert (
        hass.states.get("binary_sensor.test_vmc_3_filter_cleaning_required").state
        == expected
    )
    mock_cloud_interface.ecocomfort3.get_filter_status.assert_not_awaited()


async def test_eco3_filter_unavailable_when_device_disappears(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_interface: AsyncMock,
    single_eco_device: IntelliClimaDevices,
) -> None:
    """A missing ECO3 has no current filter status."""
    mock_cloud_interface.get_all_device_status.return_value = single_eco_device
    await async_poll(hass, freezer)
    assert (
        hass.states.get("binary_sensor.test_vmc_3_filter_cleaning_required").state
        == STATE_UNAVAILABLE
    )


@pytest.fixture(autouse=True)
async def setup_intelliclima_binary_sensor_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
    mixed_eco_devices: IntelliClimaDevices,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the binary sensor platform."""
    mock_cloud_interface.get_all_device_status.return_value = mixed_eco_devices
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
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


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
    ("device_family", "device_id", "entity_prefix"),
    [
        pytest.param(
            "ecocomfort2_devices", "56789", "binary_sensor.test_vmc_", id="eco2"
        ),
        pytest.param(
            "ecocomfort3_devices", "33333", "binary_sensor.test_vmc_3_", id="eco3"
        ),
    ],
)
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
    mixed_eco_devices: IntelliClimaDevices,
    device_family: str,
    device_id: str,
    entity_prefix: str,
    mode_state: str,
    speed_state: str,
    flags_on: set[str],
) -> None:
    """Test each fan-state binary sensor follows its flag in the running state."""
    eco = getattr(mixed_eco_devices, device_family)[device_id]
    eco.mode_state = mode_state
    eco.speed_state = speed_state
    await async_poll(hass, freezer)

    states = {
        flag: state.state
        for flag, entity_id in FAN_STATE_ENTITY_IDS.items()
        if (
            state := hass.states.get(
                entity_id.replace("binary_sensor.test_vmc_", entity_prefix)
            )
        )
    }
    assert states == {
        flag: STATE_ON if flag in flags_on else STATE_OFF
        for flag in FAN_STATE_ENTITY_IDS
    }


@pytest.mark.parametrize(
    ("device_family", "device_id", "entity_prefix"),
    [
        pytest.param(
            "ecocomfort2_devices", "56789", "binary_sensor.test_vmc_", id="eco2"
        ),
        pytest.param(
            "ecocomfort3_devices", "33333", "binary_sensor.test_vmc_3_", id="eco3"
        ),
    ],
)
async def test_fan_state_flags_unknown_on_undefined_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mixed_eco_devices: IntelliClimaDevices,
    device_family: str,
    device_id: str,
    entity_prefix: str,
) -> None:
    """Test the fan-state binary sensors are unknown when the running state is undefined."""
    getattr(mixed_eco_devices, device_family)[device_id].mode_state = "7"
    await async_poll(hass, freezer)

    for entity_id in FAN_STATE_ENTITY_IDS.values():
        assert (
            state := hass.states.get(
                entity_id.replace("binary_sensor.test_vmc_", entity_prefix)
            )
        )
        assert state.state == STATE_UNKNOWN
