"""Test the Liebherr number platform."""

import copy
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyliebherrhomeapi import (
    Device,
    DeviceState,
    DeviceType,
    TemperatureControl,
    TemperatureUnit,
    ZonePosition,
)
from pyliebherrhomeapi.exceptions import LiebherrConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE, MOCK_DEVICE_STATE

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("init_integration")
async def test_numbers(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all number entities with multi-zone device."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_single_zone_number(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test single zone device uses device name without zone suffix."""
    device = Device(
        device_id="single_zone_id",
        nickname="Single Zone Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="K2601",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    single_zone_state = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=ZonePosition.TOP,
                name="Fridge",
                type="fridge",
                value=4,
                target=4,
                min=2,
                max=8,
                unit=TemperatureUnit.CELSIUS,
            )
        ],
    )
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        single_zone_state
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_multi_zone_with_none_position(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test multi-zone device with None zone_position falls back to base translation key."""
    device = Device(
        device_id="multi_zone_none",
        nickname="Multi Zone Fridge",
        device_type=DeviceType.COMBI,
        device_name="CBNes9999",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    multi_zone_state = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=None,  # None triggers fallback
                name="Fridge",
                type="fridge",
                value=5,
                target=4,
                min=2,
                max=8,
                unit=TemperatureUnit.CELSIUS,
            ),
            TemperatureControl(
                zone_id=2,
                zone_position=ZonePosition.BOTTOM,
                name="Freezer",
                type="freezer",
                value=-18,
                target=-18,
                min=-24,
                max=-16,
                unit=TemperatureUnit.CELSIUS,
            ),
        ],
    )
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        multi_zone_state
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Zone with None position should have base translation key
    zone1_entity = entity_registry.async_get("number.multi_zone_fridge_setpoint")
    assert zone1_entity is not None
    assert zone1_entity.translation_key == "setpoint_temperature"

    # Zone with valid position should have zone-specific translation key
    zone2_entity = entity_registry.async_get(
        "number.multi_zone_fridge_bottom_zone_setpoint"
    )
    assert zone2_entity is not None
    assert zone2_entity.translation_key == "setpoint_temperature_bottom_zone"


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test setting the temperature."""
    entity_id = "number.test_fridge_top_zone_setpoint"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 6},
        blocking=True,
    )

    mock_liebherr_client.set_temperature.assert_called_once_with(
        device_id="test_device_id",
        zone_id=1,
        target=6,
        unit=TemperatureUnit.CELSIUS,
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test setting temperature fails gracefully."""
    entity_id = "number.test_fridge_top_zone_setpoint"

    mock_liebherr_client.set_temperature.side_effect = LiebherrConnectionError(
        "Connection failed"
    )

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with the device: Connection failed",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 6},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_number_update_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test number becomes unavailable when coordinator update fails and recovers."""
    entity_id = "number.test_fridge_top_zone_setpoint"

    # Initial state should be available with value
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "4"

    # Simulate update error
    mock_liebherr_client.get_device_state.side_effect = LiebherrConnectionError(
        "Connection failed"
    )

    # Advance time to trigger coordinator refresh (60 second interval)
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Number should now be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate recovery
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        MOCK_DEVICE_STATE
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Number should recover
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "4"


@pytest.mark.usefixtures("init_integration")
async def test_number_when_control_missing(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test number entity behavior when temperature control is removed."""
    entity_id = "number.test_fridge_top_zone_setpoint"

    # Initial values should be from the control
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "4"
    assert state.attributes["min"] == 2
    assert state.attributes["max"] == 8
    assert state.attributes["unit_of_measurement"] == "°C"

    # Device stops reporting controls
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE, controls=[]
    )

    # Advance time to trigger coordinator refresh
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # State should be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_number_with_none_min_max(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test number entity returns defaults when control has None min/max."""
    device = Device(
        device_id="none_min_max_device",
        nickname="Test Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="K2601",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    none_min_max_state = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=ZonePosition.TOP,
                name="Fridge",
                type="fridge",
                value=4,
                target=4,
                min=None,  # None min
                max=None,  # None max
                unit=TemperatureUnit.CELSIUS,
            )
        ],
    )
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        none_min_max_state
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "number.test_fridge_setpoint"
    state = hass.states.get(entity_id)
    assert state is not None

    # Should return defaults when min/max are None
    assert state.attributes["min"] == DEFAULT_MIN_VALUE
    assert state.attributes["max"] == DEFAULT_MAX_VALUE
