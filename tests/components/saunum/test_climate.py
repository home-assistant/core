"""Test the Saunum climate platform."""

from __future__ import annotations

from dataclasses import replace

from freezegun.api import FrozenDateTimeFactory
from pysaunum import SaunumException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "service_data", "client_method", "expected_args"),
    [
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            "async_start_session",
            (),
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            "async_stop_session",
            (),
        ),
        (
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 85},
            "async_set_target_temperature",
            (85,),
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_climate_service_calls(
    hass: HomeAssistant,
    mock_saunum_client,
    service: str,
    service_data: dict,
    client_method: str,
    expected_args: tuple,
) -> None:
    """Test climate service calls."""
    entity_id = "climate.saunum_leil"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    getattr(mock_saunum_client, client_method).assert_called_once_with(*expected_args)


@pytest.mark.parametrize(
    ("heater_elements_active", "expected_hvac_action"),
    [
        (3, HVACAction.HEATING),
        (0, HVACAction.IDLE),
    ],
)
async def test_climate_hvac_actions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    heater_elements_active: int,
    expected_hvac_action: HVACAction,
) -> None:
    """Test climate HVAC actions when session is active."""
    # Get the existing mock data and modify only what we need
    mock_saunum_client.async_get_data.return_value.session_active = True
    mock_saunum_client.async_get_data.return_value.heater_elements_active = (
        heater_elements_active
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_HVAC_ACTION) == expected_hvac_action


@pytest.mark.parametrize(
    (
        "current_temperature",
        "target_temperature",
        "expected_current",
        "expected_target",
    ),
    [
        (None, 80, None, 80),
        (35.0, 30, 35, 30),
    ],
)
async def test_climate_temperature_edge_cases(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    current_temperature: float | None,
    target_temperature: int,
    expected_current: float | None,
    expected_target: int,
) -> None:
    """Test climate with edge case temperature values."""
    # Get the existing mock data and modify only what we need
    base_data = mock_saunum_client.async_get_data.return_value
    mock_saunum_client.async_get_data.return_value = replace(
        base_data,
        current_temperature=current_temperature,
        target_temperature=target_temperature,
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == expected_current
    assert state.attributes.get(ATTR_TEMPERATURE) == expected_target


@pytest.mark.usefixtures("init_integration")
async def test_entity_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_saunum_client,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entity becomes unavailable when coordinator update fails."""
    entity_id = "climate.saunum_leil"

    # Verify entity is initially available
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Make the next update fail
    mock_saunum_client.async_get_data.side_effect = SaunumException("Read error")

    # Move time forward to trigger a coordinator update (60 seconds)
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Entity should now be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_hvac_mode_error_handling(
    hass: HomeAssistant,
    mock_saunum_client,
) -> None:
    """Test error handling when setting HVAC mode fails."""
    entity_id = "climate.saunum_leil"

    # Make the client method raise an exception
    mock_saunum_client.async_start_session.side_effect = SaunumException(
        "Communication error"
    )

    # Try to call the service and expect HomeAssistantError
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )

    # Verify the exception has the correct translation key
    assert exc_info.value.translation_key == "set_hvac_mode_failed"
    assert exc_info.value.translation_domain == "saunum"


@pytest.mark.usefixtures("init_integration")
async def test_temperature_error_handling(
    hass: HomeAssistant,
    mock_saunum_client,
) -> None:
    """Test error handling when setting temperature fails."""
    entity_id = "climate.saunum_leil"

    # Make the client method raise an exception
    mock_saunum_client.async_set_target_temperature.side_effect = SaunumException(
        "Communication error"
    )

    # Try to call the service and expect HomeAssistantError
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 85},
            blocking=True,
        )

    # Verify the exception has the correct translation key
    assert exc_info.value.translation_key == "set_temperature_failed"
    assert exc_info.value.translation_domain == "saunum"


@pytest.mark.parametrize(
    ("fan_speed", "fan_mode"),
    [
        (0, FAN_OFF),
        (1, FAN_LOW),
        (2, FAN_MEDIUM),
        (3, FAN_HIGH),
        (None, None),
    ],
)
async def test_fan_mode_read(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    fan_speed: int | None,
    fan_mode: str | None,
) -> None:
    """Test fan mode states mapping from device."""
    # Set up initial state with the fan_speed and active session
    mock_saunum_client.async_get_data.return_value.fan_speed = fan_speed
    mock_saunum_client.async_get_data.return_value.session_active = True

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    # Test reading fan mode
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


@pytest.mark.parametrize(
    ("fan_speed", "fan_mode"),
    [
        (0, FAN_OFF),
        (1, FAN_LOW),
        (2, FAN_MEDIUM),
        (3, FAN_HIGH),
    ],
)
async def test_fan_mode_write(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    fan_speed: int,
    fan_mode: str,
) -> None:
    """Test setting fan mode."""
    # Ensure session is active so fan mode can be changed
    mock_saunum_client.async_get_data.return_value.session_active = True

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    mock_saunum_client.async_set_fan_speed.assert_called_once_with(fan_speed)


@pytest.mark.usefixtures("init_integration")
async def test_fan_mode_session_not_active_error(
    hass: HomeAssistant,
    mock_saunum_client,
) -> None:
    """Test fan mode validation error when session is not active."""
    # Set session state to inactive
    mock_saunum_client.async_get_data.return_value.session_active = False

    entity_id = "climate.saunum_leil"

    # Try to set fan mode and expect error
    with pytest.raises(
        ServiceValidationError,
        match="Cannot change fan mode when sauna session is not active",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_LOW},
            blocking=True,
        )
