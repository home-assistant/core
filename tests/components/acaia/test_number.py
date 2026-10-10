"""Tests for the acaia number entities."""

from collections.abc import Callable, Generator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.acaia import coordinator as acaia_coordinator
from homeassistant.components.acaia.const import CONF_IDLE_TIMEOUT
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "number.kitchen_lunar_ddeeff_idle_disconnect_timeout"
SWITCH_ENTITY_ID = "switch.kitchen_lunar_ddeeff_keep_connected"


@pytest.fixture
def bluetooth_callbacks() -> Generator[dict[str, Callable[..., None]]]:
    """Capture the bluetooth unavailable and advertisement callbacks."""
    callbacks: dict[str, Callable[..., None]] = {}

    def _track_unavailable(
        hass: HomeAssistant, callback: Callable[..., None], *args: Any
    ) -> Callable[[], None]:
        callbacks["unavailable"] = callback
        return lambda: None

    def _register_callback(
        hass: HomeAssistant, callback: Callable[..., None], *args: Any, **kwargs: Any
    ) -> Callable[[], None]:
        callbacks["advertisement"] = callback
        return lambda: None

    with (
        patch.object(acaia_coordinator, "async_track_unavailable", _track_unavailable),
        patch.object(acaia_coordinator, "async_register_callback", _register_callback),
    ):
        yield callbacks


async def _set_idle_timeout(hass: HomeAssistant, minutes: int) -> None:
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_VALUE: minutes},
        blocking=True,
    )


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _idle_disconnect(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_scale: MagicMock
) -> None:
    """Let the scale sit idle until the integration disconnects from it."""
    await _set_idle_timeout(hass, 5)
    await _tick(hass, freezer, timedelta(minutes=5))
    mock_scale.disconnect.assert_called_once()
    mock_scale.connected = False
    mock_scale.connect.reset_mock()


async def test_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the acaia number entities."""

    with patch("homeassistant.components.acaia.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_idle_timeout_persists_to_options(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the idle timeout stores it in the config entry options."""

    await setup_integration(hass, mock_config_entry)
    await _set_idle_timeout(hass, 10)

    assert mock_config_entry.options[CONF_IDLE_TIMEOUT] == 10
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "10"


async def test_idle_timeout_available_while_scale_disconnected(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the idle timeout can be changed while the scale is disconnected."""

    await setup_integration(hass, mock_config_entry)
    mock_scale.connected = False
    await _set_idle_timeout(hass, 10)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("bluetooth_callbacks")
async def test_no_idle_disconnect_by_default(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the scale stays connected when no idle timeout is set."""

    await setup_integration(hass, mock_config_entry)
    await _tick(hass, freezer, timedelta(hours=2))

    mock_scale.disconnect.assert_not_called()


@pytest.mark.usefixtures("bluetooth_callbacks")
async def test_weight_change_resets_idle_timer(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a weight change postpones the idle disconnect."""

    await setup_integration(hass, mock_config_entry)
    notify_callback = acaia_coordinator.AcaiaScale.call_args.kwargs["notify_callback"]
    await _set_idle_timeout(hass, 5)

    await _tick(hass, freezer, timedelta(minutes=4))
    mock_scale.weight = 18.0
    notify_callback()
    await _tick(hass, freezer, timedelta(minutes=4))
    mock_scale.disconnect.assert_not_called()

    # An unchanged weight reading does not count as activity.
    notify_callback()
    await _tick(hass, freezer, timedelta(minutes=1))
    mock_scale.disconnect.assert_called_once()


async def test_reconnects_after_scale_sleeps_and_wakes(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    bluetooth_callbacks: dict[str, Callable[..., None]],
) -> None:
    """Test the scale is only reconnected once it went to sleep and came back."""

    await setup_integration(hass, mock_config_entry)
    await _idle_disconnect(hass, freezer, mock_scale)

    # The scale is still awake and advertising, so it must be left alone.
    bluetooth_callbacks["advertisement"](MagicMock(), MagicMock())
    await _tick(hass, freezer, timedelta(minutes=10))
    mock_scale.connect.assert_not_called()

    bluetooth_callbacks["unavailable"](MagicMock())
    await _tick(hass, freezer, timedelta(minutes=10))
    mock_scale.connect.assert_not_called()

    bluetooth_callbacks["advertisement"](MagicMock(), MagicMock())
    await hass.async_block_till_done()
    mock_scale.connect.assert_called_once()


async def test_unavailable_while_connected_does_not_trigger_reconnect(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    bluetooth_callbacks: dict[str, Callable[..., None]],
) -> None:
    """Test going unavailable before an idle disconnect is not treated as sleep."""

    await setup_integration(hass, mock_config_entry)
    bluetooth_callbacks["unavailable"](MagicMock())
    await _idle_disconnect(hass, freezer, mock_scale)

    bluetooth_callbacks["advertisement"](MagicMock(), MagicMock())
    await _tick(hass, freezer, timedelta(minutes=1))
    mock_scale.connect.assert_not_called()


@pytest.mark.usefixtures("bluetooth_callbacks")
async def test_disabling_idle_timeout_reconnects(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test disabling the idle timeout reconnects an idle-disconnected scale."""

    await setup_integration(hass, mock_config_entry)
    await _idle_disconnect(hass, freezer, mock_scale)

    await _set_idle_timeout(hass, 0)

    mock_scale.connect.assert_called_once()


@pytest.mark.usefixtures("bluetooth_callbacks")
async def test_turning_on_keep_connected_reconnects(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turning on keep_connected overrides an idle disconnect."""

    await setup_integration(hass, mock_config_entry)
    await _idle_disconnect(hass, freezer, mock_scale)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )

    mock_scale.connect.assert_called_once()
