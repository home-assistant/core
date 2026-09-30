"""Test the SteamVR Base Station power switch."""

from unittest.mock import ANY, AsyncMock

from lighthouse_ble import (
    BaseStationV2,
    LighthouseAdvertisement,
    LighthouseConnectionError,
    PowerState,
    Version,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import TEST_NAME, make_service_info, payload

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info_bleak

SWITCH = "switch.lhb_747a9bc5"


async def test_switch_entity(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the switch entity."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(0x0B, STATE_ON, id="on"),
        pytest.param(0x08, STATE_ON, id="booting"),
        pytest.param(0x02, STATE_OFF, id="standby"),
        pytest.param(0x00, STATE_OFF, id="sleep"),
        pytest.param(0x77, STATE_UNKNOWN, id="unknown_code"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_state_follows_advertisements(
    hass: HomeAssistant, code: int, expected: str
) -> None:
    """Test the switch reflects the advertised power state."""
    inject_bluetooth_service_info_bleak(hass, make_service_info(payload(power=code)))
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == expected


@pytest.mark.parametrize(
    ("service", "target"),
    [
        pytest.param(SERVICE_TURN_ON, PowerState.ON, id="on"),
        pytest.param(SERVICE_TURN_OFF, PowerState.SLEEP, id="off_sleeps"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_turn_on_off(
    hass: HomeAssistant, mock_set_power: AsyncMock, service: str, target: PowerState
) -> None:
    """Test turning the station on and off sends the right power command."""
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: SWITCH}, blocking=True
    )
    mock_set_power.assert_awaited_once_with(ANY, target)


async def test_command_updates_state(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_set_power: AsyncMock
) -> None:
    """Test the switch shows the new state as soon as a command succeeds."""

    async def apply(station: BaseStationV2, target: PowerState) -> None:
        station.update_from_advertisement(
            LighthouseAdvertisement(Version.V2, TEST_NAME, power=target)
        )

    mock_set_power.side_effect = apply
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: SWITCH}, blocking=True
    )
    assert hass.states.get(SWITCH).state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_command_error(hass: HomeAssistant, mock_set_power: AsyncMock) -> None:
    """Test a failed command raises a translated error and keeps the state."""
    mock_set_power.side_effect = LighthouseConnectionError("gone")
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: SWITCH}, blocking=True
        )
    assert raised.value.translation_key == "cannot_connect"
    assert hass.states.get(SWITCH).state == STATE_ON
