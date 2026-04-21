"""Test Adax climate entity."""

from homeassistant.components.adax.const import SCAN_INTERVAL
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import CLOUD_DEVICE_DATA

from tests.common import AsyncMock, MockConfigEntry, async_fire_time_changed
from tests.test_setup import FrozenDateTimeFactory


async def test_climate_cloud(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    mock_adax_cloud: AsyncMock,
) -> None:
    """Test states of the (cloud) Climate entity."""
    await setup_integration(hass, mock_cloud_config_entry)
    mock_adax_cloud.fetch_rooms_info.assert_called_once()

    assert len(hass.states.async_entity_ids(Platform.CLIMATE)) == 1
    entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.HEAT
    assert (
        state.attributes[ATTR_TEMPERATURE] == CLOUD_DEVICE_DATA[0]["targetTemperature"]
    )
    assert (
        state.attributes[ATTR_CURRENT_TEMPERATURE]
        == CLOUD_DEVICE_DATA[0]["temperature"]
    )

    mock_adax_cloud.fetch_rooms_info.side_effect = Exception()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_climate_local(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_local_config_entry: MockConfigEntry,
    mock_adax_local: AsyncMock,
) -> None:
    """Test states of the (local) Climate entity."""
    await setup_integration(hass, mock_local_config_entry)
    mock_adax_local.get_status.assert_called_once()

    assert len(hass.states.async_entity_ids(Platform.CLIMATE)) == 1
    entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 20
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 15

    mock_adax_local.get_status.side_effect = Exception()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_climate_local_initial_state_from_first_refresh(
    hass: HomeAssistant,
    mock_local_config_entry: MockConfigEntry,
    mock_adax_local: AsyncMock,
) -> None:
    """Test that local climate state is initialized from first refresh data."""
    await setup_integration(hass, mock_local_config_entry)

    assert len(hass.states.async_entity_ids(Platform.CLIMATE)) == 1
    entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]

    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 20
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 15


async def test_climate_local_initial_state_off_from_first_refresh(
    hass: HomeAssistant,
    mock_local_config_entry: MockConfigEntry,
    mock_adax_local: AsyncMock,
) -> None:
    """Test that local climate initializes correctly when first refresh reports off."""
    mock_adax_local.get_status.return_value["target_temperature"] = 0

    await setup_integration(hass, mock_local_config_entry)

    assert len(hass.states.async_entity_ids(Platform.CLIMATE)) == 1
    entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]

    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 5
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 15


async def test_climate_local_set_hvac_mode_updates_state_immediately(
    hass: HomeAssistant,
    mock_local_config_entry: MockConfigEntry,
    mock_adax_local: AsyncMock,
) -> None:
    """Test local hvac mode service updates both device and state immediately."""
    await setup_integration(hass, mock_local_config_entry)

    entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )

    mock_adax_local.set_target_temperature.assert_called_once_with(0)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.OFF

    mock_adax_local.set_target_temperature.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    mock_adax_local.set_target_temperature.assert_called_once_with(20)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.HEAT


async def test_climate_local_set_temperature_when_off_does_not_change_hvac_mode(
    hass: HomeAssistant,
    mock_local_config_entry: MockConfigEntry,
    mock_adax_local: AsyncMock,
) -> None:
    """Test setting target temperature while off does not send command or turn on."""
    await setup_integration(hass, mock_local_config_entry)

    entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )
    mock_adax_local.set_target_temperature.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: 23,
        },
        blocking=True,
    )

    mock_adax_local.set_target_temperature.assert_not_called()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 23


async def test_climate_local_set_temperature_when_heat_calls_device(
    hass: HomeAssistant,
    mock_local_config_entry: MockConfigEntry,
    mock_adax_local: AsyncMock,
) -> None:
    """Test setting target temperature while heating calls local API."""
    await setup_integration(hass, mock_local_config_entry)

    entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: 24,
        },
        blocking=True,
    )

    mock_adax_local.set_target_temperature.assert_called_once_with(24)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 24
