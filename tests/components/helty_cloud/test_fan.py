"""Test the Helty Flow Cloud fan platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyheltycloud import (
    HeltyCloudConnectionError,
    HeltyCloudError,
    HeltyCloudNoDataError,
    VmcMode,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.components.helty_cloud.const import SCAN_INTERVAL
from homeassistant.components.helty_cloud.fan import SET_MODE_ATTEMPTS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DEVICE, make_state

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

FAN_ENTITY = "fan.vmc_soggiorno"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.helty_cloud.PLATFORMS",
        [Platform.FAN],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_preset_state(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the fan reports an active preset instead of a percentage."""
    mock_helty_cloud.get_last_telemetry.side_effect = lambda serial: make_state(
        VmcMode.NIGHT
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FAN_ENTITY)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PRESET_MODE] == "night"
    assert state.attributes[ATTR_PERCENTAGE] is None


@pytest.mark.parametrize(
    ("service", "service_data", "expected_mode", "expected_state"),
    [
        (SERVICE_TURN_ON, {}, VmcMode.SPEED_1, STATE_ON),
        (SERVICE_TURN_OFF, {}, VmcMode.OFF, STATE_OFF),
        (SERVICE_TURN_ON, {ATTR_PERCENTAGE: 100}, VmcMode.SPEED_4, STATE_ON),
        (
            SERVICE_TURN_ON,
            {ATTR_PRESET_MODE: "boost"},
            VmcMode.HYPERVENTILATION,
            STATE_ON,
        ),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 50}, VmcMode.SPEED_2, STATE_ON),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 0}, VmcMode.OFF, STATE_OFF),
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "free_cooling"},
            VmcMode.FREE_COOLING,
            STATE_ON,
        ),
    ],
)
async def test_set_mode(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, object],
    expected_mode: VmcMode,
    expected_state: str,
) -> None:
    """Test every service call reaches the cloud and updates the state."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: FAN_ENTITY, **service_data},
        blocking=True,
    )

    mock_helty_cloud.set_mode_verified.assert_awaited_once_with(
        DEVICE, expected_mode, attempts=SET_MODE_ATTEMPTS
    )
    assert hass.states.get(FAN_ENTITY).state == expected_state


async def test_set_mode_failure(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a command the panel never applied surfaces as an error."""
    await setup_integration(hass, mock_config_entry)
    mock_helty_cloud.set_mode_verified.side_effect = HeltyCloudError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: FAN_ENTITY},
            blocking=True,
        )


async def test_silent_panel_is_unavailable(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a panel that has not reported does not show a state at all."""
    mock_helty_cloud.get_last_telemetry.side_effect = HeltyCloudNoDataError
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FAN_ENTITY).state == STATE_UNAVAILABLE


async def test_unavailable_when_the_poll_fails(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a cloud that stops answering makes the entity unavailable."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(FAN_ENTITY).state == STATE_ON

    mock_helty_cloud.get_last_telemetry.side_effect = HeltyCloudConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(FAN_ENTITY).state == STATE_UNAVAILABLE
