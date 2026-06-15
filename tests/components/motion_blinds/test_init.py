"""Tests for motion_blinds __init__ and entity position polling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.motion_blinds import const
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_API_KEY = "12ab345c-d67e-8f"
TEST_MAC = "ab:bb:cc:dd:ee:ff"
TEST_STORED_INTERFACE = "192.168.1.10"


def _make_multicast(start_raises=None):
    """Build an AsyncMotionMulticast mock."""
    mc = MagicMock()
    mc.Start_listen = AsyncMock(side_effect=start_raises)
    mc.Stop_listen = MagicMock()
    mc.Unregister_motion_gateway = MagicMock()
    return mc


def _make_gateway_class(probe_result=TEST_STORED_INTERFACE):
    """Build a ConnectMotionGateway class mock."""
    gw_device = MagicMock()
    gw_device.mac = TEST_MAC
    gw_device.protocol = "0.9"
    gw_device.firmware = None
    gw_device.device_list = {}
    gw_device.blind_type_list = {}

    instance = MagicMock()
    instance.async_connect_gateway = AsyncMock(return_value=True)
    instance.async_check_interface = AsyncMock(return_value=probe_result)
    instance.gateway_device = gw_device

    return MagicMock(return_value=instance)


@pytest.fixture
def config_entry_stored_interface():
    """Config entry with a concrete stored interface."""
    return MockConfigEntry(
        domain=const.DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_API_KEY: TEST_API_KEY,
            const.CONF_INTERFACE: TEST_STORED_INTERFACE,
        },
    )


async def _do_setup(hass, config_entry, mock_mc_factory, mock_gw_cls):
    """Add entry to hass and run setup with standard patches applied."""
    config_entry.add_to_hass(hass)

    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.motion_blinds.AsyncMotionMulticast",
            side_effect=mock_mc_factory,
        ),
        patch(
            "homeassistant.components.motion_blinds.ConnectMotionGateway",
            mock_gw_cls,
        ),
        patch(
            "homeassistant.components.motion_blinds.DataUpdateCoordinatorMotionBlinds",
            return_value=mock_coord,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return result, mock_gw_cls.return_value


# ---------------------------------------------------------------------------
# __init__.py — interface validation tests
# ---------------------------------------------------------------------------


async def test_setup_stored_interface_valid_skips_probe(
    hass: HomeAssistant,
    config_entry_stored_interface: MockConfigEntry,
) -> None:
    """When Start_listen succeeds, the stored interface is used and no probe runs."""
    mock_mc = _make_multicast()
    mock_gw_cls = _make_gateway_class()

    result, gw_instance = await _do_setup(
        hass,
        config_entry_stored_interface,
        lambda **_: mock_mc,
        mock_gw_cls,
    )

    assert result is True
    gw_instance.async_check_interface.assert_not_called()


async def test_setup_stored_interface_oserror_triggers_probe(
    hass: HomeAssistant,
    config_entry_stored_interface: MockConfigEntry,
) -> None:
    """When Start_listen raises OSError the stored interface triggers a full probe."""
    # First AsyncMotionMulticast call (validation) raises; second (real listener) works.
    calls = iter([_make_multicast(start_raises=OSError), _make_multicast()])
    mock_gw_cls = _make_gateway_class()

    result, gw_instance = await _do_setup(
        hass,
        config_entry_stored_interface,
        lambda **_: next(calls),
        mock_gw_cls,
    )

    assert result is True
    gw_instance.async_check_interface.assert_called_once()


# ---------------------------------------------------------------------------
# entity.py — async_scheduled_update_request position-polling tests
# ---------------------------------------------------------------------------


async def test_position_polling_stops_when_stable(hass: HomeAssistant) -> None:
    """Polling loop terminates once the position is the same for two consecutive reads."""
    from homeassistant.components.motion_blinds.entity import MotionCoordinatorEntity

    blind = MagicMock()
    blind.position = 50
    blind.angle = None
    blind.device_type = "gateway_blind"

    coordinator = MagicMock()
    coordinator.api_lock = __import__("asyncio").Lock()
    coordinator.data = {}
    coordinator.async_update_listeners = MagicMock()

    # Patch the parent __init__ so we don't need full HA wiring.
    with patch.object(
        __import__(
            "homeassistant.helpers.update_coordinator", fromlist=["CoordinatorEntity"]
        ).CoordinatorEntity,
        "__init__",
        lambda self, coordinator: None,
    ):
        entity = object.__new__(MotionCoordinatorEntity)
        entity.hass = hass
        entity._blind = blind
        entity._api_lock = coordinator.api_lock
        entity._update_interval_moving = 5
        entity._previous_positions = []
        entity._previous_angles = []
        entity._requesting_position = None
        entity.coordinator = coordinator

    trigger_calls = 0

    async def fake_trigger():
        nonlocal trigger_calls
        trigger_calls += 1

    with (
        patch.object(
            hass,
            "async_add_executor_job",
            side_effect=lambda fn: fake_trigger(),
        ),
        patch(
            "homeassistant.components.motion_blinds.entity.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.motion_blinds.entity.async_call_later"
        ) as mock_call_later,
    ):
        # First scheduled call: only one position sample → must keep polling.
        await entity.async_scheduled_update_request()
        assert mock_call_later.called
        mock_call_later.reset_mock()

        # Second scheduled call: same position again → polling should stop.
        await entity.async_scheduled_update_request()
        mock_call_later.assert_not_called()
        assert entity._requesting_position is None


async def test_position_polling_continues_while_moving(hass: HomeAssistant) -> None:
    """Polling loop keeps going while the position is still changing."""
    from homeassistant.components.motion_blinds.entity import MotionCoordinatorEntity

    blind = MagicMock()
    blind.position = 20
    blind.angle = None
    blind.device_type = "gateway_blind"

    coordinator = MagicMock()
    coordinator.api_lock = __import__("asyncio").Lock()
    coordinator.data = {}
    coordinator.async_update_listeners = MagicMock()

    with patch.object(
        __import__(
            "homeassistant.helpers.update_coordinator", fromlist=["CoordinatorEntity"]
        ).CoordinatorEntity,
        "__init__",
        lambda self, coordinator: None,
    ):
        entity = object.__new__(MotionCoordinatorEntity)
        entity.hass = hass
        entity._blind = blind
        entity._api_lock = coordinator.api_lock
        entity._update_interval_moving = 5
        entity._previous_positions = []
        entity._previous_angles = []
        entity._requesting_position = None
        entity.coordinator = coordinator

    async def fake_trigger_and_move():
        blind.position += 10  # Simulate blind still moving

    with (
        patch.object(
            hass,
            "async_add_executor_job",
            side_effect=lambda fn: fake_trigger_and_move(),
        ),
        patch(
            "homeassistant.components.motion_blinds.entity.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.motion_blinds.entity.async_call_later"
        ) as mock_call_later,
    ):
        # Both calls see a changing position → polling must continue after each.
        await entity.async_scheduled_update_request()
        assert mock_call_later.called

        mock_call_later.reset_mock()
        await entity.async_scheduled_update_request()
        assert mock_call_later.called
