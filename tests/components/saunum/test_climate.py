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
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.saunum.const import (
    OPT_PRESET_NAME_TYPE_1,
    OPT_PRESET_NAME_TYPE_2,
    OPT_PRESET_NAME_TYPE_3,
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
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "climate.saunum_leil", **service_data},
        blocking=True,
    )

    getattr(mock_saunum_client, client_method).assert_called_once_with(*expected_args)


async def test_hvac_mode_door_open_validation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test HVAC mode validation error when door is open."""
    mock_saunum_client.async_get_data.return_value = replace(
        mock_saunum_client.async_get_data.return_value, door_open=True
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(
        ServiceValidationError,
        match="Cannot start sauna session when sauna door is open",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.saunum_leil", ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("heater_elements_active", "expected_hvac_action"),
    [
        (3, HVACAction.HEATING),
        (0, HVACAction.IDLE),
    ],
)
async def test_hvac_actions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    heater_elements_active: int,
    expected_hvac_action: HVACAction,
) -> None:
    """Test HVAC actions when session is active."""
    mock_saunum_client.async_get_data.return_value = replace(
        mock_saunum_client.async_get_data.return_value,
        session_active=True,
        heater_elements_active=heater_elements_active,
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.saunum_leil")
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
async def test_temperature_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    current_temperature: float | None,
    target_temperature: int,
    expected_current: float | None,
    expected_target: int,
) -> None:
    """Test temperature attribute handling with edge cases."""
    base_data = mock_saunum_client.async_get_data.return_value
    mock_saunum_client.async_get_data.return_value = replace(
        base_data,
        current_temperature=current_temperature,
        target_temperature=target_temperature,
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.saunum_leil")
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


@pytest.mark.parametrize(
    ("service", "service_data", "mock_method", "side_effect", "translation_key"),
    [
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            "async_start_session",
            SaunumException("Communication error"),
            "set_hvac_mode_failed",
        ),
        (
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 85},
            "async_set_target_temperature",
            SaunumException("Communication error"),
            "set_temperature_failed",
        ),
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "type_2"},
            "async_set_sauna_type",
            SaunumException("Communication error"),
            "set_preset_failed",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_service_error_handling(
    hass: HomeAssistant,
    mock_saunum_client,
    service: str,
    service_data: dict,
    mock_method: str,
    side_effect: Exception,
    translation_key: str,
) -> None:
    """Test error handling when service calls fail."""
    entity_id = "climate.saunum_leil"

    getattr(mock_saunum_client, mock_method).side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_domain == "saunum"


async def test_fan_mode_service_call(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test setting fan mode."""
    mock_saunum_client.async_get_data.return_value = replace(
        mock_saunum_client.async_get_data.return_value, session_active=True
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.saunum_leil", ATTR_FAN_MODE: FAN_LOW},
        blocking=True,
    )

    mock_saunum_client.async_set_fan_speed.assert_called_once_with(1)


@pytest.mark.usefixtures("init_integration")
async def test_preset_mode_service_call(
    hass: HomeAssistant,
    mock_saunum_client,
) -> None:
    """Test setting preset mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.saunum_leil", ATTR_PRESET_MODE: "type_2"},
        blocking=True,
    )

    mock_saunum_client.async_set_sauna_type.assert_called_once_with(1)


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
async def test_fan_mode_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    fan_speed: int | None,
    fan_mode: str | None,
) -> None:
    """Test fan mode attribute mapping from device."""
    mock_saunum_client.async_get_data.return_value = replace(
        mock_saunum_client.async_get_data.return_value,
        fan_speed=fan_speed,
        session_active=True,
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.saunum_leil")
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


@pytest.mark.usefixtures("init_integration")
async def test_fan_mode_validation_error(
    hass: HomeAssistant,
) -> None:
    """Test fan mode validation error when session is not active."""
    with pytest.raises(
        ServiceValidationError,
        match="Cannot change fan mode when sauna session is not active",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.saunum_leil", ATTR_FAN_MODE: FAN_LOW},
            blocking=True,
        )


async def test_preset_mode_validation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test preset mode validation error when session is active."""
    mock_saunum_client.async_get_data.return_value = replace(
        mock_saunum_client.async_get_data.return_value, session_active=True
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: "climate.saunum_leil", ATTR_PRESET_MODE: "type_2"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "preset_session_active"
    assert exc_info.value.translation_domain == "saunum"


@pytest.mark.parametrize(
    ("sauna_type", "expected_preset"),
    [
        (0, "type_1"),
        (1, "type_2"),
        (2, "type_3"),
        (None, "type_1"),
    ],
)
async def test_preset_mode_attributes_default_names(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    sauna_type: int | None,
    expected_preset: str,
) -> None:
    """Test preset mode attributes with default names."""
    mock_saunum_client.async_get_data.return_value = replace(
        mock_saunum_client.async_get_data.return_value, sauna_type=sauna_type
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.saunum_leil")
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == expected_preset


async def test_preset_mode_attributes_custom_names(
    hass: HomeAssistant,
    mock_saunum_client,
) -> None:
    """Test preset mode attributes with custom names."""
    custom_options = {
        OPT_PRESET_NAME_TYPE_1: "Finnish Sauna",
        OPT_PRESET_NAME_TYPE_2: "Turkish Bath",
        OPT_PRESET_NAME_TYPE_3: "Steam Room",
    }
    mock_config_entry = MockConfigEntry(
        domain="saunum",
        data={"host": "192.168.1.100"},
        options=custom_options,
        title="Saunum",
    )
    mock_saunum_client.async_get_data.return_value = replace(
        mock_saunum_client.async_get_data.return_value, sauna_type=1
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.saunum_leil")
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == "Turkish Bath"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.saunum_leil", ATTR_PRESET_MODE: "Steam Room"},
        blocking=True,
    )
    mock_saunum_client.async_set_sauna_type.assert_called_once_with(2)


async def test_preset_mode_options_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test that preset names update when options are changed."""
    entity_id = "climate.saunum_leil"

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.saunum_leil")
    assert state is not None
    assert "type_1" in state.attributes.get("preset_modes", [])

    custom_options = {
        OPT_PRESET_NAME_TYPE_1: "Custom Type 1",
        OPT_PRESET_NAME_TYPE_2: "Custom Type 2",
        OPT_PRESET_NAME_TYPE_3: "Custom Type 3",
    }
    hass.config_entries.async_update_entry(mock_config_entry, options=custom_options)
    await hass.async_block_till_done()

    state = hass.states.get("climate.saunum_leil")
    assert state is not None
    assert "Custom Type 1" in state.attributes.get("preset_modes", [])
    assert "type_1" not in state.attributes.get("preset_modes", [])
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


async def test_fan_mode_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test error handling when setting fan mode fails."""
    entity_id = "climate.saunum_leil"

    mock_saunum_client.async_get_data.return_value = replace(
        mock_saunum_client.async_get_data.return_value, session_active=True
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Make the client method raise an exception
    mock_saunum_client.async_set_fan_speed.side_effect = SaunumException(
        "Communication error"
    )

    # Try to call the service and expect HomeAssistantError
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_LOW},
            blocking=True,
        )

    # Verify the exception has the correct translation key
    assert exc_info.value.translation_key == "set_fan_mode_failed"
    assert exc_info.value.translation_domain == "saunum"
