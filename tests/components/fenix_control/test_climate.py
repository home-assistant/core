"""Test the FENIX Control climate platform."""

import dataclasses
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyfenixcontrol import FenixControlConnectionError, PresetMode
import pytest
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
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import DEVICE, DEVICE_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "climate.home_living_room"

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
async def test_unknown_preset(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unreported operating mode has no preset."""
    await _set_devices(
        hass,
        mock_fenix_client,
        freezer,
        dataclasses.replace(DEVICE, preset_mode=None),
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_PRESET_MODE] is None


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
