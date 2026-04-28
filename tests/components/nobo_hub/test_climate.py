"""Tests for the Nobø Ecohub climate platform."""

from unittest.mock import MagicMock

from pynobo import nobo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.nobo_hub.const import (
    CONF_OVERRIDE_TYPE,
    OVERRIDE_TYPE_NOW,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import fire_hub_update

from tests.common import MockConfigEntry, snapshot_platform

CLIMATE_ENTITY = "climate.living_room"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the climate platform for these tests."""
    return [Platform.CLIMATE]


@pytest.mark.usefixtures("init_integration")
async def test_climate_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """All climate entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("zone_mode", "expected_state", "expected_preset"),
    [
        (nobo.API.NAME_OFF, HVACMode.OFF, PRESET_NONE),
        (nobo.API.NAME_AWAY, HVACMode.AUTO, PRESET_AWAY),
        (nobo.API.NAME_ECO, HVACMode.AUTO, PRESET_ECO),
        (nobo.API.NAME_COMFORT, HVACMode.AUTO, PRESET_COMFORT),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_state_maps_zone_mode(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    zone_mode: str,
    expected_state: HVACMode,
    expected_preset: str,
) -> None:
    """Zone modes map to the expected HVAC mode and preset."""
    mock_nobo_hub.get_current_zone_mode.return_value = zone_mode
    await fire_hub_update(hass, mock_nobo_hub)
    state = hass.states.get(CLIMATE_ENTITY)
    assert state.state == expected_state
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset


@pytest.mark.usefixtures("init_integration")
async def test_state_override_forces_heat(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """A non-normal zone override maps to HVACMode.HEAT."""
    # Any non-NORMAL override value suffices; NAME_COMFORT is arbitrary.
    mock_nobo_hub.get_zone_override_mode.return_value = nobo.API.NAME_COMFORT
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(CLIMATE_ENTITY).state == HVACMode.HEAT


@pytest.mark.usefixtures("init_integration")
async def test_current_temperature_unknown_when_missing(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """A missing current temperature surfaces as None."""
    mock_nobo_hub.get_current_zone_temperature.return_value = None
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(CLIMATE_ENTITY).attributes[ATTR_CURRENT_TEMPERATURE] is None


@pytest.mark.parametrize(
    ("hvac_mode", "expected_override"),
    [
        (HVACMode.AUTO, nobo.API.OVERRIDE_MODE_NORMAL),
        (HVACMode.HEAT, nobo.API.OVERRIDE_MODE_COMFORT),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    hvac_mode: HVACMode,
    expected_override: str,
) -> None:
    """Each HVAC mode maps to the expected zone override."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )
    mock_nobo_hub.async_create_override.assert_called_once_with(
        expected_override,
        nobo.API.OVERRIDE_TYPE_CONSTANT,
        nobo.API.OVERRIDE_TARGET_ZONE,
        "1",
    )


@pytest.mark.parametrize(
    ("preset", "expected_mode"),
    [
        (PRESET_NONE, nobo.API.OVERRIDE_MODE_NORMAL),
        (PRESET_COMFORT, nobo.API.OVERRIDE_MODE_COMFORT),
        (PRESET_ECO, nobo.API.OVERRIDE_MODE_ECO),
        (PRESET_AWAY, nobo.API.OVERRIDE_MODE_AWAY),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    preset: str,
    expected_mode: str,
) -> None:
    """Each preset maps to the expected override mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY, ATTR_PRESET_MODE: preset},
        blocking=True,
    )
    mock_nobo_hub.async_create_override.assert_called_once_with(
        expected_mode,
        nobo.API.OVERRIDE_TYPE_CONSTANT,
        nobo.API.OVERRIDE_TARGET_ZONE,
        "1",
    )


@pytest.mark.parametrize(
    "config_entry_options",
    [{CONF_OVERRIDE_TYPE: OVERRIDE_TYPE_NOW}],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_preset_with_override_type_now(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """The override_type option flows into the zone override call."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY, ATTR_PRESET_MODE: PRESET_COMFORT},
        blocking=True,
    )
    mock_nobo_hub.async_create_override.assert_called_once_with(
        nobo.API.OVERRIDE_MODE_COMFORT,
        nobo.API.OVERRIDE_TYPE_NOW,
        nobo.API.OVERRIDE_TARGET_ZONE,
        "1",
    )


@pytest.mark.usefixtures("init_integration")
async def test_zone_removed_marks_unavailable(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """A zone removed via the Nobø app must not crash and goes unavailable."""
    mock_nobo_hub.zones.pop("1")
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(CLIMATE_ENTITY).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_updates_zone(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Setting target temperatures updates the zone on the hub."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: CLIMATE_ENTITY,
            ATTR_TARGET_TEMP_LOW: 16.4,
            ATTR_TARGET_TEMP_HIGH: 21.6,
        },
        blocking=True,
    )
    mock_nobo_hub.async_update_zone.assert_called_once_with(
        "1", temp_comfort_c=22, temp_eco_c=16
    )
