"""Test the UniFi Protect alarm control panel platform."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from uiprotect.data import (
    NVR,
    ExternalArmProfile,
    ExternalArmProfileState,
    NvrArmMode,
    NvrArmModeStatus,
    PublicStoreChange,
)
from uiprotect.exceptions import GlobalAlarmManagerError
from uiprotect.websocket import WebsocketState

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_DISARM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import PUBLIC_ONLY_ALARM_ENTITY_ID
from .utils import (
    MockUFPFixture,
    assert_entity_counts,
    init_entry,
    make_public_bootstrap,
)

ALARM_ENTITY_ID = "alarm_control_panel.unifiprotect_alarm_manager"
HOME_ENTITY_ID = "alarm_control_panel.unifiprotect_home"
NIGHT_ENTITY_ID = "alarm_control_panel.unifiprotect_night"


def _make_arm_mode(status: NvrArmModeStatus) -> Mock:
    """Create a NvrArmMode object for testing."""
    arm_mode = Mock(spec=NvrArmMode)
    arm_mode.status = status
    return arm_mode


def _make_public_bootstrap(arm_mode: Mock | None) -> Mock:
    """Create a PublicBootstrap with the given arm_mode."""
    return make_public_bootstrap(arm_mode=arm_mode)


def _make_profile(
    profile_id: str,
    title: str,
    state: ExternalArmProfileState = ExternalArmProfileState.DISARMED,
) -> Mock:
    """Create an external arm profile for testing."""
    profile = Mock(spec=ExternalArmProfile)
    profile.id = profile_id
    profile.title = title
    profile.state = state
    return profile


def _setup_external(ufp: MockUFPFixture, *profiles: Mock, live: bool = True) -> Mock:
    """Put the console in external alarm manager mode with the given profiles."""
    pb = make_public_bootstrap(
        # The NVR keeps reporting an arm mode in this mode.
        arm_mode=_make_arm_mode(NvrArmModeStatus.DISABLED),
        uses_external_alarm_manager=True,
        external_arm_profiles={profile.id: profile for profile in profiles},
    )
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb
    ufp.api.is_external_arm_profiles_live = live
    return pb


def _profiles_changed(ufp: MockUFPFixture) -> None:
    """Report a change of the external arm profile store, like the library."""
    ufp.api.subscribe_public_store_changes.call_args.args[0](
        PublicStoreChange(
            "external_arm_profiles", frozenset(), frozenset(), frozenset()
        )
    )


def _set_live(ufp: MockUFPFixture, live: bool) -> None:
    """Report a new live value of the external arm profiles, like the library."""
    ufp.api.is_external_arm_profiles_live = live
    ufp.api.subscribe_external_arm_profiles_live.call_args.args[0](live)


def _nvr_frame(ufp: MockUFPFixture, nvr: NVR) -> None:
    """Deliver an NVR frame over the public devices websocket."""
    msg = Mock()
    msg.changed_data = {}
    msg.old_obj = nvr
    msg.new_obj = nvr
    ufp.devices_ws_subscription(msg)


async def test_alarm_panel_not_created_without_public_bootstrap(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Alarm panel entity is NOT created when has_public_bootstrap is False."""
    ufp.api.has_public_bootstrap = False

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 0, 0)


async def test_alarm_panel_created_with_public_bootstrap(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    nvr: NVR,
) -> None:
    """Alarm panel entity IS created when has_public_bootstrap is True."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.DISABLED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 1, 1)

    entity = entity_registry.async_get(ALARM_ENTITY_ID)
    assert entity is not None
    assert entity.unique_id == f"{nvr.mac}_alarm"

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.DISARMED
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


@pytest.mark.parametrize(
    ("nvr_status", "expected_state"),
    [
        (NvrArmModeStatus.DISABLED, AlarmControlPanelState.DISARMED),
        (NvrArmModeStatus.UNKNOWN, AlarmControlPanelState.DISARMED),
        (NvrArmModeStatus.ARMING, AlarmControlPanelState.ARMING),
        (NvrArmModeStatus.ARMED, AlarmControlPanelState.ARMED_AWAY),
        (NvrArmModeStatus.BREACH, AlarmControlPanelState.TRIGGERED),
    ],
)
async def test_alarm_panel_state_mapping(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    nvr_status: NvrArmModeStatus,
    expected_state: AlarmControlPanelState,
) -> None:
    """Test that NvrArmModeStatus maps to correct AlarmControlPanelState."""
    arm_mode = _make_arm_mode(nvr_status)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_alarm_panel_not_created_without_arm_mode(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Alarm panel entity is NOT created on old firmware (arm_mode is None)."""
    pb = _make_public_bootstrap(arm_mode=None)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 0, 0)


async def test_alarm_panel_disarm(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Test that disarm service calls disable_arm_alarm_public."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb
    ufp.api.disable_arm_alarm_public = AsyncMock()

    await init_entry(hass, ufp, [])

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: ALARM_ENTITY_ID},
        blocking=True,
    )

    ufp.api.disable_arm_alarm_public.assert_called_once()


async def test_alarm_panel_arm_away(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Test that arm_away service calls enable_arm_alarm_public."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.DISABLED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb
    ufp.api.enable_arm_alarm_public = AsyncMock()

    await init_entry(hass, ufp, [])

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: ALARM_ENTITY_ID},
        blocking=True,
    )

    ufp.api.enable_arm_alarm_public.assert_called_once()


async def test_alarm_panel_disarm_global_manager_error(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Test that GlobalAlarmManagerError on disarm raises HomeAssistantError."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb
    ufp.api.disable_arm_alarm_public = AsyncMock(side_effect=GlobalAlarmManagerError())

    await init_entry(hass, ufp, [])

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_DISARM,
            {ATTR_ENTITY_ID: ALARM_ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == "global_alarm_manager"


async def test_alarm_panel_arm_away_global_manager_error(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Test that GlobalAlarmManagerError on arm raises HomeAssistantError."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.DISABLED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb
    ufp.api.enable_arm_alarm_public = AsyncMock(side_effect=GlobalAlarmManagerError())

    await init_entry(hass, ufp, [])

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {ATTR_ENTITY_ID: ALARM_ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == "global_alarm_manager"


async def test_alarm_panel_state_update_via_ws(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    nvr: NVR,
) -> None:
    """Test that public devices WS update triggers state refresh."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.DISABLED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.DISARMED

    # Simulate arm state change via the public devices websocket
    armed_arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb.arm_mode = armed_arm_mode

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = nvr
    mock_msg.new_obj = nvr
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY


async def test_alarm_panel_unavailable_when_arm_mode_disappears(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    nvr: NVR,
) -> None:
    """Entity becomes unavailable when arm_mode disappears after a WS update."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    # Simulate firmware downgrade / global mode switch: arm_mode becomes None
    pb.arm_mode = None

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = nvr
    mock_msg.new_obj = nvr
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_alarm_panel_unavailable_on_ws_disconnect(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Entity becomes unavailable when the public devices WebSocket disconnects."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    ufp.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY


async def test_alarm_panel_availability_decoupled_from_private_websocket(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Alarm availability follows the public WS only: private loss is a no-op."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])
    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    # A private WS loss does not affect the alarm panel.
    assert ufp.ws_state_subscription is not None
    ufp.ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    # The public WS loss does flip it unavailable.
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_public_only_nvr_websocket_updates_alarm(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """An NVR devices-websocket frame re-renders the alarm from the public arm mode."""
    await setup_public_only()

    # Flip the public arm mode, then deliver an NVR frame over the devices WS.
    ufp_public_only.api.public_bootstrap.arm_mode.status = NvrArmModeStatus.ARMED
    msg = Mock()
    msg.new_obj = ufp_public_only.api.public_bootstrap.nvr  # model == NVR
    msg.old_obj = None
    msg.changed_data = {}
    ufp_public_only.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    state = hass.states.get(PUBLIC_ONLY_ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY


async def test_public_only_ws_state_refreshes_alarm(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A public devices-websocket reconnect re-signals the NVR alarm panel."""
    await setup_public_only()

    # Drop then restore: the restore re-signals the NVR (public branch).
    ufp_public_only.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(PUBLIC_ONLY_ALARM_ENTITY_ID).state == STATE_UNAVAILABLE

    ufp_public_only.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()
    assert (
        hass.states.get(PUBLIC_ONLY_ALARM_ENTITY_ID).state
        == AlarmControlPanelState.DISARMED
    )


async def test_external_profiles_replace_nvr_panel(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    nvr: NVR,
) -> None:
    """With the external alarm manager each arm profile gets its own panel."""
    old = entity_registry.async_get_or_create(
        ALARM_DOMAIN,
        "unifiprotect",
        f"{nvr.mac}_alarm",
        config_entry=ufp.entry,
        suggested_object_id="unifiprotect_alarm_manager",
    )
    _setup_external(
        ufp,
        _make_profile("p1", "Home"),
        _make_profile("p2", "Night", ExternalArmProfileState.ARMED),
    )

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 2, 2)

    assert entity_registry.async_get(old.entity_id) is None
    entity = entity_registry.async_get(HOME_ENTITY_ID)
    assert entity is not None
    assert entity.unique_id == f"{nvr.mac}_arm_profile_p1"
    assert hass.states.get(HOME_ENTITY_ID).state == AlarmControlPanelState.DISARMED
    assert hass.states.get(NIGHT_ENTITY_ID).state == AlarmControlPanelState.ARMED_AWAY


@pytest.mark.parametrize("uses_external", [False, None])
async def test_nvr_panel_kept_without_external_alarm_manager(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    uses_external: bool | None,
) -> None:
    """The NVR panel stays unless the console reports the external alarm manager."""
    pb = _make_public_bootstrap(_make_arm_mode(NvrArmModeStatus.DISABLED))
    pb.uses_external_alarm_manager = uses_external
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 1, 1)
    assert hass.states.get(ALARM_ENTITY_ID) is not None


@pytest.mark.parametrize(
    ("profile_state", "expected_state"),
    [
        (ExternalArmProfileState.DISARMED, AlarmControlPanelState.DISARMED),
        (ExternalArmProfileState.ARMING, AlarmControlPanelState.ARMING),
        (ExternalArmProfileState.ARMED, AlarmControlPanelState.ARMED_AWAY),
        (ExternalArmProfileState.BREACHING, AlarmControlPanelState.PENDING),
        (ExternalArmProfileState.BREACHED, AlarmControlPanelState.TRIGGERED),
        (ExternalArmProfileState.UNKNOWN, STATE_UNKNOWN),
    ],
)
async def test_external_profile_state_mapping(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    profile_state: ExternalArmProfileState,
    expected_state: str,
) -> None:
    """Each external arm profile state maps to an alarm control panel state."""
    _setup_external(ufp, _make_profile("p1", "Home", profile_state))

    await init_entry(hass, ufp, [])

    assert hass.states.get(HOME_ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_ALARM_ARM_AWAY, "arm_external_arm_profile_public"),
        (SERVICE_ALARM_DISARM, "disarm_external_arm_profile_public"),
    ],
)
async def test_external_profile_arm_disarm(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    service: str,
    method: str,
) -> None:
    """Arming and disarming go to the profile of the panel."""
    _setup_external(ufp, _make_profile("p1", "Home"), _make_profile("p2", "Night"))
    api_method = AsyncMock()
    setattr(ufp.api, method, api_method)

    await init_entry(hass, ufp, [])
    await hass.services.async_call(
        ALARM_DOMAIN, service, {ATTR_ENTITY_ID: NIGHT_ENTITY_ID}, blocking=True
    )

    api_method.assert_called_once_with("p2")


async def test_external_profile_follows_store_changes(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """A changed profile updates the state and the name of its panel."""
    profile = _make_profile("p1", "Home")
    _setup_external(ufp, profile)

    await init_entry(hass, ufp, [])

    profile.state = ExternalArmProfileState.ARMED
    profile.title = "Away"
    _profiles_changed(ufp)
    await hass.async_block_till_done()

    state = hass.states.get(HOME_ENTITY_ID)
    assert state.state == AlarmControlPanelState.ARMED_AWAY
    assert state.attributes["friendly_name"] == "UnifiProtect Away"


async def test_external_profile_ignores_other_stores(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """A change of another public store does not touch the panels."""
    profile = _make_profile("p1", "Home")
    _setup_external(ufp, profile)

    await init_entry(hass, ufp, [])

    profile.state = ExternalArmProfileState.ARMED
    ufp.api.subscribe_public_store_changes.call_args.args[0](
        PublicStoreChange("liveviews", frozenset(), frozenset(), frozenset())
    )
    await hass.async_block_till_done()

    assert hass.states.get(HOME_ENTITY_ID).state == AlarmControlPanelState.DISARMED


async def test_external_profile_unavailable_while_not_live(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """A panel is only available while the profile list is live."""
    _setup_external(ufp, _make_profile("p1", "Home"), live=False)

    await init_entry(hass, ufp, [])
    assert hass.states.get(HOME_ENTITY_ID).state == STATE_UNAVAILABLE

    _set_live(ufp, True)
    await hass.async_block_till_done()
    assert hass.states.get(HOME_ENTITY_ID).state == AlarmControlPanelState.DISARMED

    _set_live(ufp, False)
    await hass.async_block_till_done()
    assert hass.states.get(HOME_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_external_profile_added_and_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
) -> None:
    """Profiles created or deleted on the console follow without a reload."""
    pb = _setup_external(ufp, _make_profile("p1", "Home"))

    await init_entry(hass, ufp, [])
    assert hass.states.get(NIGHT_ENTITY_ID) is None

    pb.external_arm_profiles["p2"] = _make_profile("p2", "Night")
    _profiles_changed(ufp)
    await hass.async_block_till_done()
    assert hass.states.get(NIGHT_ENTITY_ID).state == AlarmControlPanelState.DISARMED

    del pb.external_arm_profiles["p1"]
    _profiles_changed(ufp)
    await hass.async_block_till_done()
    assert hass.states.get(HOME_ENTITY_ID) is None
    assert entity_registry.async_get(HOME_ENTITY_ID) is None
    assert entity_registry.async_get(NIGHT_ENTITY_ID) is not None


async def test_external_profile_kept_while_list_not_live(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
) -> None:
    """A profile missing from a list that is not live keeps its panel."""
    pb = _setup_external(ufp, _make_profile("p1", "Home"), live=False)

    await init_entry(hass, ufp, [])

    del pb.external_arm_profiles["p1"]
    _profiles_changed(ufp)
    await hass.async_block_till_done()
    assert entity_registry.async_get(HOME_ENTITY_ID) is not None
    assert hass.states.get(HOME_ENTITY_ID).state == STATE_UNAVAILABLE

    _set_live(ufp, True)
    await hass.async_block_till_done()
    assert entity_registry.async_get(HOME_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("live", "removed"),
    [
        pytest.param(True, True, id="live"),
        pytest.param(False, False, id="not_live"),
    ],
)
async def test_external_profile_deleted_while_stopped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    nvr: NVR,
    live: bool,
    removed: bool,
) -> None:
    """The panel of a profile deleted while stopped goes once the list is live."""
    stale = entity_registry.async_get_or_create(
        ALARM_DOMAIN,
        "unifiprotect",
        f"{nvr.mac}_arm_profile_gone",
        config_entry=ufp.entry,
    )
    _setup_external(ufp, _make_profile("p1", "Home"), live=live)

    await init_entry(hass, ufp, [])

    assert (entity_registry.async_get(stale.entity_id) is None) is removed


async def test_profile_panels_removed_in_local_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    nvr: NVR,
) -> None:
    """A console back on its own alarm manager drops the profile panels."""
    stale = entity_registry.async_get_or_create(
        ALARM_DOMAIN,
        "unifiprotect",
        f"{nvr.mac}_arm_profile_p1",
        config_entry=ufp.entry,
    )
    pb = _make_public_bootstrap(_make_arm_mode(NvrArmModeStatus.DISABLED))
    pb.uses_external_alarm_manager = False
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    assert entity_registry.async_get(stale.entity_id) is None
    assert hass.states.get(ALARM_ENTITY_ID) is not None


@pytest.mark.parametrize(
    ("before", "after", "reloads"),
    [
        pytest.param(True, False, 1, id="to_local"),
        pytest.param(False, True, 1, id="to_external"),
        pytest.param(None, True, 1, id="unreported_to_external"),
        pytest.param(True, True, 0, id="unchanged"),
        pytest.param(None, False, 0, id="unreported_to_local"),
    ],
)
async def test_alarm_manager_mode_change_reloads(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    nvr: NVR,
    before: bool | None,
    after: bool | None,
    reloads: int,
) -> None:
    """Switching between the alarm managers reloads the entry once."""
    pb = _setup_external(ufp)
    pb.uses_external_alarm_manager = before

    await init_entry(hass, ufp, [])

    pb.uses_external_alarm_manager = after
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        _nvr_frame(ufp, nvr)
        # Not from inside the websocket callback.
        mock_reload.assert_not_called()
        _nvr_frame(ufp, nvr)
        await hass.async_block_till_done()

    assert mock_reload.call_count == reloads


async def test_public_only_external_profile(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """The profile panels attach to the public NVR without a private bootstrap."""
    api = ufp_public_only.api
    api.public_bootstrap.uses_external_alarm_manager = True
    api.public_bootstrap.external_arm_profiles = {
        "p1": _make_profile("p1", "Home", ExternalArmProfileState.ARMED)
    }
    api.is_external_arm_profiles_live = True

    await setup_public_only()

    assert hass.states.get(PUBLIC_ONLY_ALARM_ENTITY_ID) is None
    state = hass.states.get("alarm_control_panel.test_nvr_home")
    assert state.state == AlarmControlPanelState.ARMED_AWAY


async def test_profile_panels_kept_when_mode_unreported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    nvr: NVR,
) -> None:
    """A console that does not report the alarm manager mode keeps profile panels."""
    stale = entity_registry.async_get_or_create(
        ALARM_DOMAIN,
        "unifiprotect",
        f"{nvr.mac}_arm_profile_p1",
        config_entry=ufp.entry,
    )
    pb = _make_public_bootstrap(_make_arm_mode(NvrArmModeStatus.DISABLED))
    pb.uses_external_alarm_manager = None
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    assert entity_registry.async_get(stale.entity_id) is not None


async def test_external_mode_without_profiles(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """External mode without profiles has no panel, not even the NVR one."""
    _setup_external(ufp)

    await init_entry(hass, ufp, [])

    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 0, 0)


async def test_external_profile_reappears_while_not_live(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    ufp: MockUFPFixture,
) -> None:
    """A profile missing from a list that is not live keeps its one panel."""
    profile = _make_profile("p1", "Home")
    pb = _setup_external(ufp, profile, live=False)

    await init_entry(hass, ufp, [])

    del pb.external_arm_profiles["p1"]
    _profiles_changed(ufp)
    await hass.async_block_till_done()
    pb.external_arm_profiles["p1"] = profile
    _profiles_changed(ufp)
    _set_live(ufp, True)
    await hass.async_block_till_done()

    assert "does not generate unique IDs" not in caplog.text
    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 1, 1)
    assert hass.states.get(HOME_ENTITY_ID).state == AlarmControlPanelState.DISARMED


@pytest.mark.parametrize(
    ("state", "title", "expected_state", "expected_name"),
    [
        pytest.param(
            ExternalArmProfileState.ARMED,
            "Home",
            AlarmControlPanelState.ARMED_AWAY,
            "UnifiProtect Home",
            id="state",
        ),
        pytest.param(
            ExternalArmProfileState.DISARMED,
            "Away",
            AlarmControlPanelState.DISARMED,
            "UnifiProtect Away",
            id="title",
        ),
    ],
)
async def test_external_profile_single_field_change(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    state: ExternalArmProfileState,
    title: str,
    expected_state: AlarmControlPanelState,
    expected_name: str,
) -> None:
    """A change of only the state or only the title is written."""
    profile = _make_profile("p1", "Home")
    _setup_external(ufp, profile)

    await init_entry(hass, ufp, [])

    profile.state = state
    profile.title = title
    _profiles_changed(ufp)
    await hass.async_block_till_done()

    state_obj = hass.states.get(HOME_ENTITY_ID)
    assert state_obj.state == expected_state
    assert state_obj.attributes["friendly_name"] == expected_name


async def test_external_arm_subscriptions_released_on_unload(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Unloading releases the store change and live subscriptions."""
    _setup_external(ufp, _make_profile("p1", "Home"))

    await init_entry(hass, ufp, [])
    store_unsub = ufp.api.subscribe_public_store_changes.return_value
    live_unsub = ufp.api.subscribe_external_arm_profiles_live.return_value
    store_unsub.assert_not_called()
    live_unsub.assert_not_called()

    await hass.config_entries.async_unload(ufp.entry.entry_id)

    store_unsub.assert_called_once()
    live_unsub.assert_called_once()
