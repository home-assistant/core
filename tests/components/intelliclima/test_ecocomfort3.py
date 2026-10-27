"""Test ECOCOMFORT 3 support alongside ECOCOMFORT 2.0."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyintelliclima import FanMode, FanSpeed, IntelliClimaDevices
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.components.intelliclima.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import async_poll, setup_integration

FAN_ENTITY_ID = "fan.test_vmc_3"
SELECT_ENTITY_ID = "select.test_vmc_3_fan_direction_mode"
FILTER_ENTITY_ID = "binary_sensor.test_vmc_3_filter_cleaning_required"


@pytest.fixture(autouse=True)
def mock_eco3_status(
    mock_cloud_interface: AsyncMock, single_eco3_device: IntelliClimaDevices
) -> None:
    """Discover an ECOCOMFORT 3 through the real integration setup."""
    mock_cloud_interface.get_all_device_status.return_value = single_eco3_device


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Create the ECO3 entities without exposing the unreliable CO2 field."""
    await setup_integration(hass, mock_config_entry)

    for entry in er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ):
        assert entry == snapshot(name=f"{entry.entity_id}-entry")
        assert hass.states.get(entry.entity_id) == snapshot(name=entry.entity_id)
    assert (fan_entry := entity_registry.async_get(FAN_ENTITY_ID))
    assert (device := device_registry.async_get(fan_entry.device_id))
    assert device.model == "ECOCOMFORT 3"
    assert device.sw_version == "0.9.6"
    assert (DOMAIN, "33333") in device.identifiers
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 10
    )
    assert (
        hass.states.get("sensor.test_vmc_3_volatile_organic_compounds_parts").state
        == "1800.0"
    )
    mock_cloud_interface.ecocomfort2.get_filter_status.assert_not_awaited()
    mock_cloud_interface.ecocomfort3.get_filter_status.assert_not_awaited()


@pytest.mark.parametrize(
    ("mode", "speed", "percentage", "preset", "direction"),
    [
        pytest.param("3", "2", 50, None, "alternate", id="manual"),
        pytest.param("132", "18", 50, "auto", "sensor", id="auto"),
        pytest.param("1", "67", 100, None, "forward", id="boost"),
        pytest.param("2", "131", 25, None, "reverse", id="night"),
        pytest.param("0", "0", 0, None, STATE_UNKNOWN, id="off"),
    ],
)
async def test_running_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    single_eco3_device: IntelliClimaDevices,
    mode: str,
    speed: str,
    percentage: int,
    preset: str | None,
    direction: str,
) -> None:
    """Use decoded running state even when commanded setpoints differ."""
    device = single_eco3_device.ecocomfort3_devices["33333"]
    device.mode_state = mode
    device.speed_state = speed
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(FAN_ENTITY_ID))
    assert state.attributes[ATTR_PERCENTAGE] == percentage
    assert state.attributes[ATTR_PRESET_MODE] == preset
    assert hass.states.get(SELECT_ENTITY_ID).state == direction


async def test_commands_use_eco3_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Send commands through ECO3, preserving commanded rather than running values."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )
    mock_cloud_interface.ecocomfort3.turn_off.assert_awaited_once_with("AABBCCDD")

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: "auto"},
        blocking=True,
    )
    mock_cloud_interface.ecocomfort3.set_mode_speed_auto.assert_awaited_once_with(
        "AABBCCDD"
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: 75},
        blocking=True,
    )
    mock_cloud_interface.ecocomfort3.set_mode_speed.assert_awaited_with(
        "AABBCCDD", FanMode.sensor, FanSpeed.medium
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: "reverse"},
        blocking=True,
    )
    mock_cloud_interface.ecocomfort3.set_mode_speed.assert_awaited_with(
        "AABBCCDD", FanMode.outward, FanSpeed.sleep
    )
    mock_cloud_interface.ecocomfort2.turn_off.assert_not_awaited()
    mock_cloud_interface.ecocomfort2.set_mode_speed_auto.assert_not_awaited()
    mock_cloud_interface.ecocomfort2.set_mode_speed.assert_not_awaited()


async def test_turn_on_preserves_commanded_speed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
    single_eco3_device: IntelliClimaDevices,
) -> None:
    """Turning on during boost does not make the temporary boost permanent."""
    device = single_eco3_device.ecocomfort3_devices["33333"]
    device.speed_set = FanSpeed.low
    device.speed_state = "67"
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )
    mock_cloud_interface.ecocomfort3.set_mode_speed.assert_awaited_once_with(
        "AABBCCDD", FanMode.sensor, FanSpeed.low
    )


@pytest.mark.parametrize(
    ("dev_state", "expected"),
    [
        pytest.param("0", STATE_OFF, id="clean"),
        pytest.param("1", STATE_ON, id="cleaning_due"),
        pytest.param(None, STATE_UNKNOWN, id="no_reading"),
    ],
)
async def test_filter_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    single_eco3_device: IntelliClimaDevices,
    dev_state: str | None,
    expected: str,
) -> None:
    """Read the filter warning directly from the ECO3 status."""
    single_eco3_device.ecocomfort3_devices["33333"].dev_state = dev_state
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(FILTER_ENTITY_ID).state == expected


async def test_mixed_account_and_device_disappears(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
    single_eco_device: IntelliClimaDevices,
    single_eco3_device: IntelliClimaDevices,
) -> None:
    """An unavailable ECO3 does not affect ECO2 entities in the same account."""
    single_eco3_device.ecocomfort2_devices = single_eco_device.ecocomfort2_devices
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("fan.test_vmc").state == STATE_ON
    assert hass.states.get(FAN_ENTITY_ID).state == STATE_ON
    mock_cloud_interface.ecocomfort2.get_filter_status.assert_awaited_once_with(
        "11223344"
    )

    mock_cloud_interface.get_all_device_status.reset_mock()
    mock_cloud_interface.get_all_device_status.return_value = single_eco_device
    await async_poll(hass, freezer)

    mock_cloud_interface.get_all_device_status.assert_awaited_once()
    assert hass.states.get("fan.test_vmc").state == STATE_ON
    assert hass.states.get(FAN_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(FILTER_ENTITY_ID).state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("mode", "speed", "flag", "expected"),
    [
        pytest.param("3", "67", "boost", STATE_ON, id="boost"),
        pytest.param("2", "131", "night_mode", STATE_ON, id="night"),
        pytest.param("1", "34", "advanced_control", STATE_ON, id="advanced"),
        pytest.param("132", "18", "automatic_speed_control", STATE_ON, id="profiled"),
        pytest.param("3", "2", "boost", STATE_OFF, id="no_boost"),
        pytest.param("7", "2", "boost", STATE_UNKNOWN, id="undefined"),
    ],
)
async def test_fan_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    single_eco3_device: IntelliClimaDevices,
    mode: str,
    speed: str,
    flag: str,
    expected: str,
) -> None:
    """Expose decoded running flags for ECO3, including undefined registers."""
    device = single_eco3_device.ecocomfort3_devices["33333"]
    device.mode_state = mode
    device.speed_state = speed
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(f"binary_sensor.test_vmc_3_{flag}").state == expected


@pytest.mark.parametrize(
    ("field", "sentinel", "entity_id"),
    [
        pytest.param(
            "tamb", "327.67", "sensor.test_vmc_3_temperature", id="temperature"
        ),
        pytest.param("rh", "143", "sensor.test_vmc_3_humidity", id="humidity"),
        pytest.param(
            "voc_state",
            "65535",
            "sensor.test_vmc_3_volatile_organic_compounds_parts",
            id="voc",
        ),
    ],
)
async def test_no_reading(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    single_eco3_device: IntelliClimaDevices,
    field: str,
    sentinel: str,
    entity_id: str,
) -> None:
    """Do not expose protocol no-reading values as measurements."""
    setattr(single_eco3_device.ecocomfort3_devices["33333"], field, sentinel)
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
