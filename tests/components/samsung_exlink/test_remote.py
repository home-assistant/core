"""Tests for the Samsung ExLink remote platform."""

from unittest.mock import AsyncMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from samsung_exlink import CommandRejected, Key, SamsungTVError, TVState

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.components.samsung_exlink.const import DOMAIN
from homeassistant.components.samsung_exlink.coordinator import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MockSamsungTV

ENTITY_ID = "remote.samsung_tv"


@pytest.fixture(autouse=True)
async def auto_init_components(init_components: None) -> None:
    """Set up the component."""


@pytest.fixture
def samsung_exlink_platforms() -> list[Platform]:
    """Load only the remote platform."""
    return [Platform.REMOTE]


async def test_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the remote entity is created and associated with the TV device."""
    assert hass.states.get(ENTITY_ID) is not None
    entity = entity_registry.async_get(ENTITY_ID)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert entity is not None
    assert device is not None
    assert entity.device_id == device.id


async def test_power_services_and_toggle(
    hass: HomeAssistant, mock_samsung_tv: MockSamsungTV
) -> None:
    """Test power services delegate to the TV and toggle follows reported state."""
    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_samsung_tv.power_on.assert_awaited_once()

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_samsung_tv.power_off.assert_awaited_once()

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert mock_samsung_tv.power_off.await_count == 2

    off_state = TVState(power=False)
    mock_samsung_tv.mock_state(off_state)
    await hass.async_block_till_done()
    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert mock_samsung_tv.power_on.await_count == 2


async def test_polling_updates_remote_without_media_player(
    hass: HomeAssistant,
    mock_samsung_tv: MockSamsungTV,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator polls even when only the remote platform is loaded."""
    off_state = TVState(power=False)
    mock_samsung_tv.refresh.side_effect = lambda: mock_samsung_tv.mock_state(off_state)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_samsung_tv.refresh.await_count == 2
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_state_updates(
    hass: HomeAssistant, mock_samsung_tv: MockSamsungTV
) -> None:
    """Test the remote state follows TV power updates."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    off_state = TVState(power=False)
    mock_samsung_tv.mock_state(off_state)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    mock_samsung_tv.mock_state(TVState())
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_send_command_repeats(
    hass: HomeAssistant, mock_samsung_tv: MockSamsungTV
) -> None:
    """Test commands are mapped to library keys and repeated in order."""
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_COMMAND: ["KEY_POWER", "KEY_VOLUP"],
            ATTR_NUM_REPEATS: 2,
            ATTR_DELAY_SECS: 0,
        },
        blocking=True,
    )

    assert mock_samsung_tv.send_key.await_args_list == [
        call(Key.KEY_POWER),
        call(Key.KEY_VOLUP),
        call(Key.KEY_POWER),
        call(Key.KEY_VOLUP),
    ]


async def test_send_command_delay_between_commands_and_repeats(
    hass: HomeAssistant, mock_samsung_tv: MockSamsungTV
) -> None:
    """Test the send command service delays between keys and repetitions."""
    with patch(
        "homeassistant.components.samsung_exlink.remote.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_COMMAND: ["KEY_POWER", "KEY_VOLUP"],
                ATTR_NUM_REPEATS: 2,
                ATTR_DELAY_SECS: 0.2,
            },
            blocking=True,
        )

    assert mock_samsung_tv.send_key.await_args_list == [
        call(Key.KEY_POWER),
        call(Key.KEY_VOLUP),
        call(Key.KEY_POWER),
        call(Key.KEY_VOLUP),
    ]
    assert mock_sleep.await_args_list == [call(0.2)] * 3


async def test_service_key_is_not_supported(
    hass: HomeAssistant, mock_samsung_tv: MockSamsungTV
) -> None:
    """Test service-oriented keys are not available through the remote."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: "KEY_FACTORY"},
            blocking=True,
        )

    assert err.value.translation_key == "unsupported_key"
    mock_samsung_tv.send_key.assert_not_awaited()


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(CommandRejected("rejected"), "command_rejected", id="rejected"),
        pytest.param(
            SamsungTVError("unexpected response"), "command_failed", id="library"
        ),
        pytest.param(
            ConnectionError("connection lost"), "command_failed", id="connection"
        ),
        pytest.param(TimeoutError(), "command_failed", id="timeout"),
    ],
)
async def test_send_command_error(
    hass: HomeAssistant,
    mock_samsung_tv: MockSamsungTV,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test library and connection failures are translated consistently."""
    mock_samsung_tv.send_key.side_effect = exception

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: "KEY_POWER"},
            blocking=True,
        )

    assert err.value.translation_key == translation_key
