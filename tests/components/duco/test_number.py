"""Tests for the Duco number platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from duco_connectivity import (
    BypassSupplyTemperatureTarget,
    DucoError,
    DucoRateLimitError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import setup_platform_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

_ZONE_1_ENTITY_ID = "number.living_bypass_target_1"
_ZONE_2_ENTITY_ID = "number.living_bypass_target_2"
_ZONE_3_ENTITY_ID = "number.living_bypass_target_3"
_ZONE_4_ENTITY_ID = "number.living_bypass_target_4"


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> MockConfigEntry:
    """Set up only the number platform for testing."""
    return await setup_platform_integration(hass, mock_config_entry, [Platform.NUMBER])


@pytest.mark.usefixtures("init_integration")
async def test_bypass_supply_temperature_target_numbers(
    hass: HomeAssistant,
) -> None:
    """Test bypass supply temperature target numbers are created from API metadata."""
    zone_1_state = hass.states.get(_ZONE_1_ENTITY_ID)
    assert zone_1_state is not None
    assert zone_1_state.state == "20.0"
    assert zone_1_state.attributes["min"] == 15.0
    assert zone_1_state.attributes["max"] == 25.0
    assert zone_1_state.attributes["step"] == 0.1
    assert zone_1_state.attributes["unit_of_measurement"] == "°C"

    zone_2_state = hass.states.get(_ZONE_2_ENTITY_ID)
    assert zone_2_state is not None
    assert zone_2_state.state == "21.0"


async def test_bypass_supply_temperature_target_numbers_support_four_zones(
    hass: HomeAssistant,
    mock_bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget],
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test bypass target controls are created for all four supported zones."""
    mock_bypass_supply_temperature_targets.update(
        {
            3: BypassSupplyTemperatureTarget(
                zone_id=3,
                value=22.0,
                minimum=15.0,
                increment=0.1,
                maximum=25.0,
            ),
            4: BypassSupplyTemperatureTarget(
                zone_id=4,
                value=23.0,
                minimum=15.0,
                increment=0.1,
                maximum=25.0,
            ),
        }
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.NUMBER])

    for entity_id in (
        _ZONE_1_ENTITY_ID,
        _ZONE_2_ENTITY_ID,
        _ZONE_3_ENTITY_ID,
        _ZONE_4_ENTITY_ID,
    ):
        assert hass.states.get(entity_id) is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_bypass_supply_temperature_target_number_entities_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test bypass supply temperature target number entity states."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_duco_client")
async def test_bypass_supply_temperature_targets_missing_skips_number_creation(
    hass: HomeAssistant,
    mock_bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no number entities are created when bypass targets are unavailable."""
    mock_bypass_supply_temperature_targets.clear()

    await setup_platform_integration(hass, mock_config_entry, [Platform.NUMBER])

    assert hass.states.get(_ZONE_1_ENTITY_ID) is None
    assert hass.states.get(_ZONE_2_ENTITY_ID) is None


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("minimum", id="missing_minimum"),
        pytest.param("maximum", id="missing_maximum"),
        pytest.param("increment", id="missing_increment"),
    ],
)
@pytest.mark.usefixtures("mock_duco_client")
async def test_bypass_supply_temperature_target_incomplete_metadata_skips_number_creation(
    hass: HomeAssistant,
    mock_bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget],
    mock_config_entry: MockConfigEntry,
    field: str,
) -> None:
    """Test incomplete target metadata does not expose an invalid control."""
    mock_bypass_supply_temperature_targets[1] = replace(
        mock_bypass_supply_temperature_targets[1], **{field: None}
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.NUMBER])

    assert hass.states.get(_ZONE_1_ENTITY_ID) is None
    assert hass.states.get(_ZONE_2_ENTITY_ID) is not None


@pytest.mark.usefixtures("init_integration")
async def test_set_bypass_supply_temperature_target(
    hass: HomeAssistant,
    mock_bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget],
    mock_duco_client: AsyncMock,
) -> None:
    """Test setting a bypass target refreshes the number from the box."""

    async def async_set_bypass_supply_temperature_target(
        zone_id: int,
        temperature: float,
    ) -> BypassSupplyTemperatureTarget:
        target = replace(
            mock_bypass_supply_temperature_targets[zone_id], value=temperature
        )

        mock_bypass_supply_temperature_targets[zone_id] = target
        return target

    mock_duco_client.async_set_bypass_supply_temperature_target.side_effect = (
        async_set_bypass_supply_temperature_target
    )

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: _ZONE_1_ENTITY_ID, "value": 20.5},
        blocking=True,
    )

    mock_duco_client.async_set_bypass_supply_temperature_target.assert_called_once_with(
        1, 20.5
    )
    state = hass.states.get(_ZONE_1_ENTITY_ID)
    assert state is not None
    assert state.state == "20.5"


async def test_set_bypass_supply_temperature_target_honors_increment_metadata(
    hass: HomeAssistant,
    mock_bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget],
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test bypass target writes follow the API-provided increment metadata."""
    mock_bypass_supply_temperature_targets[1] = replace(
        mock_bypass_supply_temperature_targets[1],
        minimum=10.0,
        increment=0.5,
        maximum=25.5,
    )

    async def async_set_bypass_supply_temperature_target(
        zone_id: int,
        temperature: float,
    ) -> BypassSupplyTemperatureTarget:
        target = replace(
            mock_bypass_supply_temperature_targets[zone_id], value=temperature
        )

        mock_bypass_supply_temperature_targets[zone_id] = target
        return target

    mock_duco_client.async_set_bypass_supply_temperature_target.side_effect = (
        async_set_bypass_supply_temperature_target
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.NUMBER])

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: _ZONE_1_ENTITY_ID, "value": 20.5},
        blocking=True,
    )

    mock_duco_client.async_set_bypass_supply_temperature_target.assert_called_once_with(
        1, 20.5
    )

    with pytest.raises(
        HomeAssistantError,
        match="supported increment of 0.5 starting at 10.0",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: _ZONE_1_ENTITY_ID, "value": 20.2},
            blocking=True,
        )


async def test_set_bypass_supply_temperature_target_in_fahrenheit_units(
    hass: HomeAssistant,
    mock_bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget],
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test Fahrenheit service writes normalize to the nearest supported Celsius step."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_bypass_supply_temperature_targets[1] = replace(
        mock_bypass_supply_temperature_targets[1],
        minimum=10.0,
        increment=0.5,
        maximum=25.5,
    )

    async def async_set_bypass_supply_temperature_target(
        zone_id: int,
        temperature: float,
    ) -> BypassSupplyTemperatureTarget:
        target = replace(
            mock_bypass_supply_temperature_targets[zone_id], value=temperature
        )

        mock_bypass_supply_temperature_targets[zone_id] = target
        return target

    mock_duco_client.async_set_bypass_supply_temperature_target.side_effect = (
        async_set_bypass_supply_temperature_target
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.NUMBER])

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: _ZONE_1_ENTITY_ID, "value": 69.0},
        blocking=True,
    )

    mock_duco_client.async_set_bypass_supply_temperature_target.assert_called_once_with(
        1, 20.5
    )
    state = hass.states.get(_ZONE_1_ENTITY_ID)
    assert state is not None
    assert state.state == "68.9"


async def test_bypass_supply_temperature_target_becomes_unavailable_when_omitted(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget],
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test an existing bypass target becomes unavailable when the zone omits it."""
    zone_1_available = True

    async def async_get_bypass_supply_temperature_target(
        zone_id: int,
    ) -> BypassSupplyTemperatureTarget | None:
        if zone_id == 1 and not zone_1_available:
            return None
        return mock_bypass_supply_temperature_targets.get(zone_id)

    mock_duco_client.async_get_bypass_supply_temperature_target.side_effect = (
        async_get_bypass_supply_temperature_target
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.NUMBER])

    state = hass.states.get(_ZONE_1_ENTITY_ID)
    assert state is not None
    assert state.state == "20.0"

    zone_1_available = False
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(_ZONE_1_ENTITY_ID)
    assert state is not None
    assert state.state is STATE_UNAVAILABLE

    zone_1_available = True
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(_ZONE_1_ENTITY_ID)
    assert state is not None
    assert state.state == "20.0"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("exception", "match"),
    [
        pytest.param(
            DucoError("Unexpected error"),
            "Failed to set bypass supply target temperature",
            id="duco_error",
        ),
        pytest.param(DucoRateLimitError(), "daily write limit", id="rate_limit"),
    ],
)
async def test_set_bypass_supply_temperature_target_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    exception: Exception,
    match: str,
) -> None:
    """Test write failures raise translated Home Assistant errors."""
    mock_duco_client.async_set_bypass_supply_temperature_target = AsyncMock(
        side_effect=exception
    )

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: _ZONE_1_ENTITY_ID, "value": 20.5},
            blocking=True,
        )
