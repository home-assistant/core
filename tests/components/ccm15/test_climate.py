"""Unit test for CCM15 coordinator component."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from ccm15 import CCM15DeviceState, CCM15SlaveDevice, TriState
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_ON,
    SWING_OFF,
    SWING_ON,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_climate_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    ccm15_device: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("climate.midea_0") == snapshot
    assert entity_registry.async_get("climate.midea_1") == snapshot

    assert hass.states.get("climate.midea_0") == snapshot
    assert hass.states.get("climate.midea_1") == snapshot

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ["climate.midea_0"], ATTR_FAN_MODE: FAN_HIGH},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ["climate.midea_0"], ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ["climate.midea_0"],
                ATTR_TEMPERATURE: 25,
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ["climate.midea_0"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ["climate.midea_0"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    # The next poll returns no devices.
    ccm15_device.return_value = CCM15DeviceState(devices={})
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get("climate.midea_0") == snapshot
    assert entity_registry.async_get("climate.midea_1") == snapshot

    assert hass.states.get("climate.midea_0") == snapshot
    assert hass.states.get("climate.midea_1") == snapshot


async def test_entity_unavailable_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    ccm15_device: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """When a slot stops reporting, the entity is unavailable and its attrs are None."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("climate.midea_0").state != STATE_UNAVAILABLE

    # The slot stops reporting: the next poll returns no devices.
    ccm15_device.return_value = CCM15DeviceState(devices={})
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("climate.midea_0").state == STATE_UNAVAILABLE

    entity = hass.data[CLIMATE_DOMAIN].get_entity("climate.midea_0")
    assert entity is not None
    assert entity.available is False
    assert entity.current_temperature is None
    assert entity.target_temperature is None
    assert entity.hvac_mode is None
    assert entity.fan_mode is None
    assert entity.swing_mode is None
    assert entity.extra_state_attributes == {}


async def test_climate_fahrenheit_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    ccm15_device: AsyncMock,
) -> None:
    """A controller set to Fahrenheit is reported in Fahrenheit."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    ccm15_device.return_value = CCM15DeviceState(
        devices={0: CCM15SlaveDevice(bytes.fromhex("01000041c0004b"))}
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The entity must report the device's Fahrenheit unit, not hardcoded Celsius.
    climate_component = hass.data[CLIMATE_DOMAIN]
    entity = climate_component.get_entity("climate.midea_0")
    assert entity is not None
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT

    # With the entity already in Fahrenheit under the US system, the device's
    # native values pass through unconverted; were it still Celsius they would
    # be converted and differ.
    state = hass.states.get("climate.midea_0")
    assert state is not None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 75
    assert state.attributes[ATTR_TEMPERATURE] == 86


@pytest.mark.usefixtures("ccm15_device")
@pytest.mark.parametrize(
    ("swing_mode", "expected"),
    [(SWING_ON, TriState.ON), (SWING_OFF, TriState.OFF)],
)
async def test_climate_set_swing_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    swing_mode: str,
    expected: TriState,
) -> None:
    """Setting the swing mode sends the desired swing to the device."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: ["climate.midea_0"], ATTR_SWING_MODE: swing_mode},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()
        # The opt-in swing TriState must be set so the library emits `sw`.
        data = mock_set_state.call_args.args[1]
        assert data.desired_swing is expected
