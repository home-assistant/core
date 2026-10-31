"""Test the FENIX Control climate platform."""

import dataclasses
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyfenixcontrol import Device, FenixControlConnectionError, PresetMode
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.fenix_control.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import DEVICE, DEVICE_ID

ENTITY_ID = "climate.home_living_room"

OFF_DEVICE = dataclasses.replace(DEVICE, preset_mode=int(PresetMode.OFF))
HOLIDAY_DEVICE = dataclasses.replace(
    DEVICE,
    preset_mode=int(PresetMode.HOLIDAYS),
    hvac_state=2,
    holiday_start="01/12/2025 12:00:00",
    holiday_end="10/12/2025 12:00:00",
    holiday_mode=2,
    active_holiday_mode=2,
)


async def _set_devices(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    *devices: object,
) -> None:
    """Return new device states on the next poll."""
    mock_fenix_client.get_devices.return_value = list(devices)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.fixture
def platforms() -> list[Platform]:
    """Load only the climate platform."""
    return [Platform.CLIMATE]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the climate entity."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature(
    hass: HomeAssistant, mock_fenix_client: MagicMock
) -> None:
    """Test setting the target temperature."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 21.5},
        blocking=True,
    )

    mock_fenix_client.set_target_temperature.assert_awaited_once_with(DEVICE_ID, 21.5)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] == 21.5
    assert state.state == HVACMode.HEAT


@pytest.mark.usefixtures("init_integration")
async def test_command_keeps_poll_schedule(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an optimistic update doesn't postpone the next poll."""
    # Align the poll schedule with the frozen clock
    await _set_devices(hass, mock_fenix_client, freezer, DEVICE)
    polls = mock_fenix_client.get_devices.call_count

    freezer.tick(SCAN_INTERVAL - timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 21.5},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 21.5
    assert mock_fenix_client.get_devices.call_count == polls

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_fenix_client.get_devices.call_count == polls + 1


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "preset_mode"),
    [
        (HVACMode.OFF, PresetMode.OFF),
        (HVACMode.AUTO, PresetMode.PROGRAM),
    ],
)
async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    hvac_mode: HVACMode,
    preset_mode: PresetMode,
) -> None:
    """Test the HVAC mode is applied after the temperature, which selects manual."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 21.5, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    mock_fenix_client.set_target_temperature.assert_awaited_once_with(DEVICE_ID, 21.5)
    mock_fenix_client.set_preset_mode.assert_awaited_once_with(DEVICE_ID, preset_mode)
    state = hass.states.get(ENTITY_ID)
    assert state.state == hvac_mode


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_with_heat_mode(
    hass: HomeAssistant, mock_fenix_client: MagicMock
) -> None:
    """Test heat needs no extra command, the temperature already selects manual."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 21.5,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    mock_fenix_client.set_target_temperature.assert_awaited_once_with(DEVICE_ID, 21.5)
    mock_fenix_client.set_preset_mode.assert_not_called()
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_with_unsupported_hvac_mode(
    hass: HomeAssistant, mock_fenix_client: MagicMock
) -> None:
    """Test an unsupported HVAC mode is rejected before any command is sent."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 21.5,
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "unsupported_hvac_mode"
    mock_fenix_client.set_target_temperature.assert_not_called()
    mock_fenix_client.set_preset_mode.assert_not_called()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "preset_mode"),
    [
        (HVACMode.OFF, PresetMode.OFF),
        (HVACMode.AUTO, PresetMode.PROGRAM),
        (HVACMode.HEAT, PresetMode.MANUAL),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    hvac_mode: HVACMode,
    preset_mode: PresetMode,
) -> None:
    """Test setting the HVAC mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    mock_fenix_client.set_preset_mode.assert_awaited_once_with(DEVICE_ID, preset_mode)
    assert hass.states.get(ENTITY_ID).state == hvac_mode


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("last_mode", "expected_mode"),
    [
        pytest.param(PresetMode.MANUAL, PresetMode.MANUAL, id="heat"),
        pytest.param(PresetMode.PROGRAM, PresetMode.PROGRAM, id="auto"),
        pytest.param(PresetMode.DEFROST, PresetMode.PROGRAM, id="preset"),
    ],
)
async def test_turn_on_restores_last_mode(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    last_mode: PresetMode,
    expected_mode: PresetMode,
) -> None:
    """Test turning on restores the last HVAC mode in which it was on."""
    await _set_devices(
        hass,
        mock_fenix_client,
        freezer,
        dataclasses.replace(DEVICE, preset_mode=last_mode),
    )
    await _set_devices(hass, mock_fenix_client, freezer, OFF_DEVICE)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_fenix_client.set_preset_mode.assert_awaited_once_with(DEVICE_ID, expected_mode)


async def test_turn_on_defaults_to_program(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fenix_client: MagicMock,
) -> None:
    """Test turning on a thermostat that was off since startup starts the program."""
    mock_fenix_client.get_devices.return_value = [OFF_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_fenix_client.set_preset_mode.assert_awaited_once_with(
        DEVICE_ID, PresetMode.PROGRAM
    )
    assert hass.states.get(ENTITY_ID).state == HVACMode.AUTO


@pytest.mark.usefixtures("init_integration")
async def test_turn_off(hass: HomeAssistant, mock_fenix_client: MagicMock) -> None:
    """Test turning off switches the thermostat off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_fenix_client.set_preset_mode.assert_awaited_once_with(
        DEVICE_ID, PresetMode.OFF
    )
    assert hass.states.get(ENTITY_ID).state == HVACMode.OFF


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("preset", "preset_mode"),
    [
        (PRESET_HOME, PresetMode.PROGRAM),
        (PRESET_AWAY, PresetMode.DEFROST),
        (PRESET_BOOST, PresetMode.BOOST),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    preset: str,
    preset_mode: PresetMode,
) -> None:
    """Test setting a preset."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    mock_fenix_client.set_preset_mode.assert_awaited_once_with(DEVICE_ID, preset_mode)
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_PRESET_MODE] == preset


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "data", "client_method", "translation_key"),
    [
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 21.0},
            "set_target_temperature",
            "set_temperature_failed",
            id="temperature",
        ),
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            "set_preset_mode",
            "set_hvac_mode_failed",
            id="hvac_mode",
        ),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_AWAY},
            "set_preset_mode",
            "set_preset_mode_failed",
            id="preset",
        ),
    ],
)
async def test_command_errors(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    service: str,
    data: dict[str, object],
    client_method: str,
    translation_key: str,
) -> None:
    """Test a failed command raises a translated error and keeps the state."""
    getattr(mock_fenix_client, client_method).side_effect = FenixControlConnectionError(
        "offline"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **data},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT


@pytest.mark.usefixtures("init_integration")
async def test_holiday_locks_controls(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an active holiday locks the thermostat."""
    await _set_devices(hass, mock_fenix_client, freezer, HOLIDAY_DEVICE)

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.AUTO]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    # Without supported features Home Assistant omits these attributes
    assert ATTR_HVAC_ACTION not in state.attributes
    assert ATTR_PRESET_MODE not in state.attributes

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.AUTO},
            blocking=True,
        )

    assert exc_info.value.translation_key == "holiday_active"
    mock_fenix_client.set_preset_mode.assert_not_called()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_state", "hvac_action"),
    [
        (0, HVACAction.IDLE),
        (1, HVACAction.HEATING),
        (2, HVACAction.OFF),
        (7, None),
        (None, None),
    ],
)
async def test_hvac_action(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    hvac_state: int | None,
    hvac_action: HVACAction | None,
) -> None:
    """Test the heating state is mapped to the HVAC action."""
    await _set_devices(
        hass,
        mock_fenix_client,
        freezer,
        dataclasses.replace(DEVICE, hvac_state=hvac_state),
    )

    # Home Assistant omits the attribute when the action is unknown
    assert hass.states.get(ENTITY_ID).attributes.get(ATTR_HVAC_ACTION) == hvac_action


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("device", "hvac_modes"),
    [
        pytest.param(
            dataclasses.replace(DEVICE, preset_mode=None),
            [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT],
            id="unreported",
        ),
        pytest.param(
            dataclasses.replace(DEVICE, preset_mode=3),
            [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT],
            id="unrecognized",
        ),
        pytest.param(
            dataclasses.replace(HOLIDAY_DEVICE, preset_mode=None),
            [],
            id="holiday",
        ),
    ],
)
async def test_unknown_preset(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    device: Device,
    hvac_modes: list[HVACMode],
) -> None:
    """Test an unreported or unrecognized operating mode is unknown."""
    await _set_devices(hass, mock_fenix_client, freezer, device)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    # A holiday removes the preset feature, so the attribute is omitted
    assert state.attributes.get(ATTR_PRESET_MODE) is None
    assert state.attributes[ATTR_HVAC_MODES] == hvac_modes


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_skips_unknown_mode(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unknown operating mode doesn't replace the last mode it was on in."""
    await _set_devices(
        hass, mock_fenix_client, freezer, dataclasses.replace(DEVICE, preset_mode=None)
    )
    await _set_devices(hass, mock_fenix_client, freezer, OFF_DEVICE)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_fenix_client.set_preset_mode.assert_awaited_once_with(
        DEVICE_ID, PresetMode.MANUAL
    )


@pytest.mark.usefixtures("init_integration")
async def test_device_removed(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a thermostat no longer reported by the cloud becomes unavailable."""
    await _set_devices(hass, mock_fenix_client, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_cloud_unavailable(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the thermostat is unavailable while the cloud can't be reached."""
    mock_fenix_client.get_installations.side_effect = FenixControlConnectionError(
        "offline"
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_fenix_client.get_installations.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT
