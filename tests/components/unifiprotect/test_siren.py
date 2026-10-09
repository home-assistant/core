"""Tests for the UniFi Protect siren (Public API) entities."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from uiprotect.data import DeviceState, ModelType, Siren, SirenDuration, WSAction
from uiprotect.exceptions import (
    BadRequest,
    ClientError,
    NotAuthorized,
    PublicOnlyModeError,
)
from uiprotect.websocket import WebsocketState

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_VOLUME_LEVEL,
    DOMAIN as SIREN_DOMAIN,
)
from homeassistant.components.unifiprotect.const import (
    CONF_CONNECTION_MODE,
    CONNECTION_MODE_API_KEY_ONLY,
    DOMAIN,
)
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .utils import (
    MockUFPFixture,
    assert_entity_counts,
    init_entry,
    make_public_bootstrap,
)

SIREN_ID = "siren-id-1"
SIREN_MAC = "AA:BB:CC:DD:EE:02"
SIREN_NAME = "Garage Siren"

SIREN_ENTITY_ID = "siren.garage_siren"


def _make_siren(
    *, is_active: bool = False, state: DeviceState = DeviceState.CONNECTED
) -> Mock:
    """Build a mock :class:`Siren`."""
    siren = Mock(spec=Siren)
    siren.id = SIREN_ID
    siren.mac = SIREN_MAC
    siren.name = SIREN_NAME
    siren.model = ModelType.SIREN
    siren.state = state
    siren.volume = 50
    siren.is_active = is_active
    siren.play = AsyncMock()
    siren.stop = AsyncMock()
    siren.set_volume = AsyncMock()
    return siren


def _make_public_bootstrap(siren: Mock | None) -> Mock:
    """Build a public bootstrap mock with the given siren."""
    return make_public_bootstrap(sirens={siren.id: siren} if siren is not None else {})


def _make_ws_msg(siren: Mock, *, deleted: bool = False) -> Mock:
    """Build a minimal WS subscription message for siren tests."""
    msg = Mock()
    msg.changed_data = {}
    msg.old_obj = siren
    msg.new_obj = None if deleted else siren
    return msg


@pytest.fixture(name="siren")
def _siren_fixture() -> Mock:
    """Build a mock Siren."""
    return _make_siren()


@pytest.fixture(name="ufp_with_siren")
def _ufp_with_siren(ufp: MockUFPFixture, siren: Mock) -> MockUFPFixture:
    """Configure ufp fixture with a single siren accessible via public API."""
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(siren)
    return ufp


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def test_siren_not_created_without_public_bootstrap(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """No siren entity is created when public bootstrap is unavailable."""
    ufp.api.has_public_bootstrap = False
    await init_entry(hass, ufp, [])

    assert_entity_counts(hass, Platform.SIREN, 0, 0)


async def test_siren_ws_update_without_subscription_is_ignored(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """A public siren WS update for an unsubscribed siren is a no-op."""
    await init_entry(hass, ufp, [])
    assert ufp.devices_ws_subscription is not None

    ufp.devices_ws_subscription(_make_ws_msg(_make_siren()))
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SIREN, 0, 0)


async def test_siren_created_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """Siren entity is created with state off when siren is idle."""
    await init_entry(hass, ufp_with_siren, [])

    entry = entity_registry.async_get(SIREN_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{SIREN_MAC}_siren"

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_siren_created_on(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Siren entity is created with state on when siren is active."""
    siren.is_active = True

    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_siren_device_links_to_nvr_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """Siren device's via_device_id points at the NVR device."""
    await init_entry(hass, ufp_with_siren, [])

    nvr = ufp_with_siren.api.bootstrap.nvr
    nvr_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, nvr.mac), ufp_with_siren.entry.entry_id
    )
    assert nvr_device is not None

    siren_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SIREN_MAC), ufp_with_siren.entry.entry_id
    )
    assert siren_device is not None
    assert siren_device.via_device_id == nvr_device.id


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def test_siren_turn_on(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Calling turn_on activates the siren via play()."""
    await init_entry(hass, ufp_with_siren, [])

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
        blocking=True,
    )
    siren.play.assert_awaited_once_with(duration=None)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (5, SirenDuration.FIVE),
        (10, SirenDuration.TEN),
        (20, SirenDuration.TWENTY),
        (30, SirenDuration.THIRTY),
    ],
)
async def test_siren_turn_on_with_duration(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
    seconds: int,
    expected: SirenDuration,
) -> None:
    """Valid duration to turn_on calls play with matching SirenDuration."""
    await init_entry(hass, ufp_with_siren, [])

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID, ATTR_DURATION: seconds},
        blocking=True,
    )
    siren.play.assert_awaited_once_with(duration=expected)


async def test_siren_turn_on_invalid_duration(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Passing an unsupported duration raises ServiceValidationError."""
    await init_entry(hass, ufp_with_siren, [])

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SIREN_ENTITY_ID, ATTR_DURATION: 15},
            blocking=True,
        )
    siren.play.assert_not_awaited()


async def test_siren_turn_on_invalid_duration_does_not_set_volume(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Duration is validated before set_volume is called.

    When both an invalid duration and a volume are given, neither set_volume nor
    play must be called — duration validation must happen first.
    """
    await init_entry(hass, ufp_with_siren, [])

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: SIREN_ENTITY_ID,
                ATTR_DURATION: 15,
                ATTR_VOLUME_LEVEL: 0.5,
            },
            blocking=True,
        )
    siren.set_volume.assert_not_awaited()
    siren.play.assert_not_awaited()


async def test_siren_turn_on_with_volume(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Passing volume_level to turn_on calls set_volume before play."""
    await init_entry(hass, ufp_with_siren, [])

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID, ATTR_VOLUME_LEVEL: 0.75},
        blocking=True,
    )
    siren.set_volume.assert_awaited_once_with(75)
    siren.play.assert_awaited_once_with(duration=None)


async def test_siren_turn_off(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Calling turn_off stops the siren via stop() and immediately sets state to off."""
    siren.is_active = True
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
        blocking=True,
    )
    siren.stop.assert_awaited_once()
    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [NotAuthorized("denied"), ClientError("timeout")],
)
async def test_siren_turn_on_api_error(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
    exc: Exception,
) -> None:
    """API errors from play() are wrapped as HomeAssistantError."""
    await init_entry(hass, ufp_with_siren, [])

    siren.play.side_effect = exc

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
            blocking=True,
        )


async def test_siren_turn_on_when_siren_gone(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """Command raises HomeAssistantError when siren is no longer in bootstrap."""
    await init_entry(hass, ufp_with_siren, [])

    ufp_with_siren.api.public_bootstrap.sirens = {}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
            blocking=True,
        )


async def test_siren_turn_off_when_bootstrap_unavailable(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """Command raises HomeAssistantError when has_public_bootstrap is False."""
    await init_entry(hass, ufp_with_siren, [])

    ufp_with_siren.api.has_public_bootstrap = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# WebSocket state updates
# ---------------------------------------------------------------------------


async def test_siren_state_updates_from_public_ws(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Public devices WS updates flip the entity on and back off."""
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    siren.is_active = True

    mock_msg = _make_ws_msg(siren)
    assert ufp_with_siren.devices_ws_subscription is not None
    ufp_with_siren.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # A timed run ending arrives the same way, as an update with the flag off.
    siren.is_active = False
    ufp_with_siren.devices_ws_subscription(_make_ws_msg(siren))
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_siren_ws_update_no_state_change(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """WS update with identical state leaves the entity state unchanged."""
    siren.is_active = True
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    mock_msg = _make_ws_msg(siren)
    assert ufp_with_siren.devices_ws_subscription is not None
    ufp_with_siren.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_siren_availability_follows_websocket_state(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """Siren entity becomes unavailable on WS disconnect and recovers on reconnect."""
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    assert ufp_with_siren.devices_ws_state_subscription is not None
    ufp_with_siren.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    ufp_with_siren.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "state",
    [DeviceState.DISCONNECTED, DeviceState.CONNECTING, DeviceState.UNKNOWN],
)
async def test_siren_unavailable_when_not_connected_at_setup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    state: DeviceState,
) -> None:
    """A siren that is not connected at setup starts out unavailable."""
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(_make_siren(state=state))

    await init_entry(hass, ufp, [])

    assert hass.states.get(SIREN_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_siren_unavailable_when_disconnected(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """A siren that drops off the console is unavailable, and recovers."""
    await init_entry(hass, ufp_with_siren, [])
    assert hass.states.get(SIREN_ENTITY_ID).state == STATE_OFF

    siren.state = DeviceState.DISCONNECTED
    ufp_with_siren.devices_ws_subscription(_make_ws_msg(siren))
    await hass.async_block_till_done()

    assert hass.states.get(SIREN_ENTITY_ID).state == STATE_UNAVAILABLE

    siren.state = DeviceState.CONNECTED
    ufp_with_siren.devices_ws_subscription(_make_ws_msg(siren))
    await hass.async_block_till_done()

    assert hass.states.get(SIREN_ENTITY_ID).state == STATE_OFF


async def test_siren_unavailable_on_delete_event(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Entity becomes UNAVAILABLE when the siren is removed via a WS delete event.

    On a delete event (new_obj=None) data.py dispatches None to the public
    subscriptions for the old object's mac. The entity re-reads self._siren;
    since it is no longer in the bootstrap it must override _attr_available
    to False.
    """
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    # Remove the siren from the public bootstrap so _siren returns None.
    del ufp_with_siren.api.public_bootstrap.sirens[SIREN_ID]

    # Simulate a WS delete event: new_obj=None, old_obj=last-known siren.
    mock_msg = _make_ws_msg(siren, deleted=True)
    assert ufp_with_siren.devices_ws_subscription is not None
    ufp_with_siren.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.fixture(name="setup_hybrid")
def setup_hybrid_fixture(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Return a callable setting up the hybrid entry without a siren."""
    ufp.api.has_public_bootstrap = True
    pb = _make_public_bootstrap(None)
    ufp.api.public_bootstrap = pb
    ufp.api.update_public = AsyncMock(return_value=pb)

    async def _setup() -> None:
        await init_entry(hass, ufp, [])

    return _setup


def _add_siren_frame(ufp: MockUFPFixture, siren: Mock) -> None:
    """Deliver a public devices websocket add frame for ``siren``."""
    ufp.api.public_bootstrap.sirens[siren.id] = siren
    msg = _make_ws_msg(siren)
    msg.action = WSAction.ADD
    ufp.devices_ws_subscription(msg)


@pytest.mark.parametrize(
    ("ufp_fixture", "setup_fixture"),
    [
        pytest.param("ufp_public_only", "setup_public_only", id="public_only"),
        pytest.param("ufp", "setup_hybrid", id="hybrid"),
    ],
)
async def test_siren_added_after_setup(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    entity_registry: er.EntityRegistry,
    ufp_fixture: str,
    setup_fixture: str,
    siren: Mock,
) -> None:
    """A siren adopted after setup gets its entity in both modes.

    The private bootstrap has no store for sirens, so the adopt path never
    sees one; discovery goes through the public add signal in both modes.
    """
    ufp: MockUFPFixture = request.getfixturevalue(ufp_fixture)
    setup: Callable[[], Coroutine[Any, Any, None]] = request.getfixturevalue(
        setup_fixture
    )
    await setup()
    assert entity_registry.async_get(SIREN_ENTITY_ID) is None

    _add_siren_frame(ufp, siren)
    await hass.async_block_till_done()

    assert entity_registry.async_get(SIREN_ENTITY_ID) is not None


async def test_public_only_siren_end_to_end(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    siren: Mock,
) -> None:
    """An API-key-only entry with a siren creates a working entity.

    Exercises the real public-only setup path: reading the private bootstrap
    raises on that client, so the siren platform must not touch it.
    """
    ufp_public_only.api.public_bootstrap.sirens = {siren.id: siren}

    await setup_public_only()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    # Commands go to the public object; there is no private one to fall back to.
    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
        blocking=True,
    )
    siren.play.assert_awaited_once_with(duration=None)


async def test_siren_survives_switch_to_public_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """An entry switched to API-key-only keeps its siren entity.

    The entity is built from the public object in both modes, so after the
    switch the existing registry entry is re-adopted instead of being left
    behind without an entity.
    """
    ufp = ufp_with_siren
    await init_entry(hass, ufp, [])
    registry_entry = entity_registry.async_get(SIREN_ENTITY_ID)
    assert registry_entry is not None
    assert hass.states.get(SIREN_ENTITY_ID).state == STATE_OFF

    await hass.config_entries.async_unload(ufp.entry.entry_id)
    await hass.async_block_till_done()

    # The public-only setup path registers the NVR from the public bootstrap.
    api = ufp.api
    api.public_bootstrap.nvr = api.bootstrap.nvr

    # Flip both the stored mode and the client, as reconfiguring does.
    hass.config_entries.async_update_entry(
        ufp.entry,
        data={**ufp.entry.data, CONF_CONNECTION_MODE: CONNECTION_MODE_API_KEY_ONLY},
    )
    api.is_public_only = True
    type(api).bootstrap = PropertyMock(side_effect=BadRequest("public-only"))
    api.update = AsyncMock(side_effect=PublicOnlyModeError("public-only"))
    api.update_public = AsyncMock(return_value=api.public_bootstrap)

    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=api,
    ):
        await hass.config_entries.async_setup(ufp.entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get(SIREN_ENTITY_ID).id == registry_entry.id
    assert hass.states.get(SIREN_ENTITY_ID).state == STATE_OFF
