"""The tests for the denonavr select platform."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from denonavr.exceptions import AvrCommandError, AvrNetworkError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.denonavr.config_flow import (
    CONF_MANUFACTURER,
    CONF_SERIAL_NUMBER,
    CONF_TYPE,
    DOMAIN,
)
from homeassistant.components.denonavr.const import (
    CONF_UPDATE_AUDYSSEY,
    CONF_USE_TELNET,
    COORDINATOR_UPDATE_INTERVAL,
)
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    CONF_HOST,
    CONF_MODEL,
    SERVICE_SELECT_OPTION,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_HOST = "1.2.3.4"
TEST_NAME = "Test_Receiver"
TEST_MODEL = "model5"
TEST_SERIALNUMBER = "123456789"
TEST_MANUFACTURER = "Denon"
TEST_RECEIVER_TYPE = "avr-x"
TEST_ZONE = "Main"
TEST_UNIQUE_ID = f"{TEST_MODEL}-{TEST_SERIALNUMBER}"


@pytest.fixture(autouse=True)
def _fast_action_refresh_debounce():
    """Patch the action-refresh debounce cooldown down for every test.

    The real cooldown is a short but real delay before the confirming
    fetch. No test here is about that timing, so it is patched away to
    keep the suite fast and deterministic.
    """
    with patch(
        "homeassistant.components.denonavr.coordinator.ACTION_REFRESH_DEBOUNCE_COOLDOWN",
        0,
    ):
        yield


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with (
        patch(
            "homeassistant.components.denonavr.receiver.DenonAVR",
            autospec=True,
        ) as mock_client_class,
        patch("homeassistant.components.denonavr.config_flow.denonavr.async_discover"),
    ):
        mock_client_class.return_value.name = TEST_NAME
        mock_client_class.return_value.model_name = TEST_MODEL
        mock_client_class.return_value.serial_number = TEST_SERIALNUMBER
        mock_client_class.return_value.manufacturer = TEST_MANUFACTURER
        mock_client_class.return_value.receiver_type = TEST_RECEIVER_TYPE
        mock_client_class.return_value.zone = TEST_ZONE
        mock_client_class.return_value.input_func_list = []
        mock_client_class.return_value.sound_mode_list = []
        mock_client_class.return_value.zones = {"Main": mock_client_class.return_value}
        mock_client_class.return_value.telnet_connected = False
        mock_client_class.return_value.telnet_healthy = False

        # Audyssey defaults used by the select entities.
        mock_client_class.return_value.dynamic_eq = True
        mock_client_class.return_value.reference_level_offset = "0dB"
        mock_client_class.return_value.reference_level_offset_setting_list = [
            "0dB",
            "+5dB",
            "+10dB",
            "+15dB",
        ]
        mock_client_class.return_value.dynamic_volume = "Off"
        mock_client_class.return_value.dynamic_volume_setting_list = [
            "Off",
            "Light",
            "Medium",
            "Heavy",
        ]
        mock_client_class.return_value.multi_eq = "Reference"
        mock_client_class.return_value.multi_eq_setting_list = [
            "Off",
            "Flat",
            "L/R Bypass",
            "Reference",
            "Manual",
        ]
        mock_client_class.return_value.eco_mode = "Auto"
        mock_client_class.return_value.dimmer = "Bright"
        mock_client_class.return_value.auto_standby = "OFF"
        yield mock_client_class.return_value


async def setup_denonavr(
    hass: HomeAssistant, options: dict | None = None
) -> MockConfigEntry:
    """Initialize the denonavr integration for tests."""
    entry_data = {
        CONF_HOST: TEST_HOST,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
    }

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data=entry_data,
        options=options or {},
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    return mock_entry


async def _wait_for_debounced_refresh(hass: HomeAssistant) -> None:
    """Let a coordinator's debounced confirmation refresh actually fire.

    A debounced request schedules a raw event-loop timer rather than a
    tracked task, so async_block_till_done() alone does not wait for it.
    One tick is enough with the cooldown patched to 0.
    """
    await asyncio.sleep(0)
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, key: str, domain: str = SELECT_DOMAIN) -> str:
    """Look up an entity_id by its unique_id suffix."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{TEST_UNIQUE_ID}-{key}")
    assert entity_id is not None
    return entity_id


async def test_reference_level_offset_state(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the reference level offset select reports the receiver's state."""
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, "reference_level_offset")
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0dB"
    assert state.attributes["options"] == ["0dB", "+5dB", "+10dB", "+15dB"]


async def test_reference_level_offset_unavailable_when_dynamic_eq_off(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the reference level offset select is unavailable without Dynamic EQ."""
    client.dynamic_eq = False
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, "reference_level_offset")
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"


async def test_set_reference_level_offset(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test selecting a new reference level offset."""
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, "reference_level_offset")
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "+5dB"},
        blocking=True,
    )

    client.async_set_reflevoffset.assert_awaited_once_with("+5dB")


async def test_set_reference_level_offset_raises_on_avr_error(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test that a receiver error is surfaced to the user."""
    await setup_denonavr(hass)
    entity_id = _entity_id(hass, "reference_level_offset")

    client.async_set_reflevoffset.side_effect = AvrCommandError(
        "Reference level could only be set when DynamicEQ is active", "SetAudyssey"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "+5dB"},
            blocking=True,
        )


async def test_connectivity_error_during_action_marks_unavailable(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A connectivity failure while sending a command marks it unavailable.

    Unlike a rejected command (AvrCommandError, see the test above),
    this indicates the receiver itself is unreachable - the entity
    shouldn't keep showing available with stale data until the next
    scheduled poll happens to notice.
    """
    await setup_denonavr(hass)
    entity_id = _entity_id(hass, "reference_level_offset")
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    client.async_set_reflevoffset.side_effect = AvrNetworkError(
        "Connection refused", "SetAudyssey"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "+5dB"},
            blocking=True,
        )

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_connectivity_error_during_audyssey_action_marks_general_unavailable(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """An Audyssey action's connectivity failure also marks the general coordinator.

    An unreachable receiver found through an Audyssey-backed action is the
    same news as one found through a media_player command, so the entities
    on the general coordinator must not keep showing stale data.
    """
    entry = await setup_denonavr(hass)
    entity_id = _entity_id(hass, "reference_level_offset")

    client.async_set_reflevoffset.side_effect = AvrNetworkError(
        "Connection refused", "SetAudyssey"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "+5dB"},
            blocking=True,
        )

    assert entry.runtime_data.coordinator.last_update_success is False


async def test_general_failure_marks_audyssey_unavailable_even_while_polling(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A general connectivity failure also marks Audyssey unavailable immediately.

    Even when "Update Audyssey settings" is on and the Audyssey
    coordinator has its own recurring poll - a receiver-wide failure
    shouldn't leave Audyssey entities showing available with stale
    data until that poll happens to notice on its own schedule.
    """
    entry = await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: True})

    client.async_update.side_effect = AvrNetworkError("Connection refused", "GET")
    await entry.runtime_data.coordinator.async_refresh()

    assert entry.runtime_data.audyssey_coordinator.last_update_success is False


async def test_dynamic_volume(hass: HomeAssistant, client: MagicMock) -> None:
    """Test the dynamic volume select reads and writes correctly."""
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, "dynamic_volume")
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Off"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Heavy"},
        blocking=True,
    )
    client.async_set_dynamicvol.assert_awaited_once_with("Heavy")


async def test_multi_eq(hass: HomeAssistant, client: MagicMock) -> None:
    """Test the Multi-EQ select reads and writes correctly."""
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, "multi_eq")
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Reference"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Flat"},
        blocking=True,
    )
    client.async_set_multieq.assert_awaited_once_with("Flat")


async def test_eco_mode(hass: HomeAssistant, client: MagicMock) -> None:
    """Test the Eco Mode select reads and writes correctly."""
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, "eco_mode")
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Auto"
    assert state.attributes["options"] == ["On", "Auto", "Off"]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "On"},
        blocking=True,
    )
    client.async_eco_mode.assert_awaited_once_with("On")


async def test_dimmer(hass: HomeAssistant, client: MagicMock) -> None:
    """Test the Dimmer select reads and writes correctly."""
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, "dimmer")
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Bright"
    assert state.attributes["options"] == ["Off", "Dark", "Dim", "Bright"]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
        blocking=True,
    )
    client.async_dimmer.assert_awaited_once_with("Dark")


async def test_auto_standby(hass: HomeAssistant, client: MagicMock) -> None:
    """Test the Auto Standby select reads and writes correctly."""
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, "auto_standby")
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "OFF"
    assert state.attributes["options"] == [
        "OFF",
        "15M",
        "30M",
        "60M",
        "2H",
        "4H",
        "8H",
    ]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "30M"},
        blocking=True,
    )
    client.async_auto_standby.assert_awaited_once_with("30M")


async def test_unavailable_after_connectivity_error_then_recovers(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A connectivity-type refresh failure marks the entity unavailable.

    A rejected command does not, and a later successful refresh recovers.
    Calls async_refresh() directly because the assertions need a
    synchronous refresh rather than the debounced one an action uses.
    """
    entry = await setup_denonavr(hass)
    entity_id = _entity_id(hass, "dimmer")
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    client.async_update.side_effect = AvrNetworkError("Connection refused", "GET")
    await entry.runtime_data.coordinator.async_refresh()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    client.async_update.side_effect = None
    await entry.runtime_data.coordinator.async_refresh()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_dimmer_refreshes_and_shows_new_state_immediately(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test that a stale immediate refresh doesn't revert a just-set value."""
    await setup_denonavr(hass)
    entity_id = _entity_id(hass, "dimmer")
    assert client.dimmer == "Bright"

    async def _apply_dimmer_change(*args, **kwargs):
        client.dimmer = "Dark"

    # An async function, since AsyncMock only auto-awaits one, installed
    # after setup so its initial refresh does not already flip dimmer.
    client.async_update.side_effect = _apply_dimmer_change

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
        blocking=True,
    )
    # blocking=True only waits for the service handler itself - see
    # _wait_for_debounced_refresh for why this extra step is needed.
    await _wait_for_debounced_refresh(hass)

    # One call from setup's initial refresh, one from confirming this
    # action (CoordinatorEntity sets should_poll=False, so there's no
    # separate forced poll on top of that)...
    assert client.async_update.await_count == 2
    # ...and the new value is visible right away, with no time-based
    # polling trick needed to observe it.
    assert hass.states.get(entity_id).state == "Dark"


async def test_eco_mode_and_auto_standby_also_refresh_immediately(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Eco mode and auto standby also show the new value immediately."""
    await setup_denonavr(hass)
    baseline_calls = client.async_update.await_count

    eco_entity_id = _entity_id(hass, "eco_mode")
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: eco_entity_id, ATTR_OPTION: "Off"},
        blocking=True,
    )
    await _wait_for_debounced_refresh(hass)
    client.async_update.assert_awaited()

    standby_entity_id = _entity_id(hass, "auto_standby")
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: standby_entity_id, ATTR_OPTION: "15M"},
        blocking=True,
    )
    await _wait_for_debounced_refresh(hass)
    # One call per action - CoordinatorEntity sets should_poll=False, so
    # there's no separate forced poll on top of our own explicit
    # confirmation the way a plain polling entity would get.
    assert client.async_update.await_count == baseline_calls + 2


async def test_reference_level_offset_always_refreshes_after_change(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Audyssey-group settings always force-refresh after a change.

    "Update Audyssey settings" governs the recurring poll alone, and it is
    off by default, so gating this refresh on it would leave the UI showing
    the old value of a change the receiver did apply.
    """
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: False})
    entity_id = _entity_id(hass, "reference_level_offset")

    # Setup does one initial Audyssey fetch per config entry, so both
    # entities start with a real value rather than unavailable.
    baseline_calls = client.async_update_audyssey.await_count

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "+5dB"},
        blocking=True,
    )
    await _wait_for_debounced_refresh(hass)
    # Just one call, since this is the only entity acting - HA's own
    # post-service-call poll doesn't apply here (should_poll=False).
    assert client.async_update_audyssey.await_count == baseline_calls + 1


async def test_coordinators_serialize_command_and_refresh(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A select action and an Audyssey refresh on the shared lock don't overlap.

    Running a command concurrently with a refresh on the other coordinator
    proves the shared lock serializes them, which asserting that the two
    lock objects are identical would not.
    """
    entry = await setup_denonavr(hass)
    entity_id = _entity_id(hass, "dimmer")

    call_order = []

    async def _slow_dimmer_set(option: str) -> None:
        call_order.append("start-dimmer")
        await asyncio.sleep(0.05)
        client.dimmer = option
        call_order.append("end-dimmer")

    async def _slow_audyssey_update() -> None:
        call_order.append("start-audyssey")
        await asyncio.sleep(0.05)
        call_order.append("end-audyssey")

    client.async_dimmer.side_effect = _slow_dimmer_set
    client.async_update_audyssey.side_effect = _slow_audyssey_update

    await asyncio.gather(
        hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
            blocking=True,
        ),
        entry.runtime_data.audyssey_coordinator.async_refresh(),
    )

    assert call_order in (
        ["start-dimmer", "end-dimmer", "start-audyssey", "end-audyssey"],
        ["start-audyssey", "end-audyssey", "start-dimmer", "end-dimmer"],
    )


async def test_audyssey_coordinator_polls_when_option_on(
    hass: HomeAssistant, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """The Audyssey coordinator actually polls on a schedule when the option is on.

    Exercises the real behavior (a call once the interval elapses)
    rather than just asserting update_interval was set, which would
    still pass even if the recurring poll's own listener registration
    were broken.
    """
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: True})
    calls_before = client.async_update_audyssey.await_count

    freezer.tick(timedelta(seconds=COORDINATOR_UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_update_audyssey.await_count > calls_before


async def test_audyssey_coordinator_skips_poll_when_telnet_healthy(
    hass: HomeAssistant, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A scheduled Audyssey poll is skipped once Telnet already keeps it current.

    Mirrors async_refresh_status's own guard for the general
    coordinator - Telnet already pushes these settings live (see
    __init__.py's Telnet listener), so a receiver where this HTTP
    query takes ~10s shouldn't be hit with it again every interval.
    """
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: True})
    client.telnet_connected = True
    client.telnet_healthy = True
    calls_before = client.async_update_audyssey.await_count

    freezer.tick(timedelta(seconds=COORDINATOR_UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_update_audyssey.await_count == calls_before


async def test_audyssey_coordinator_does_not_poll_when_option_off(
    hass: HomeAssistant, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Confirms it doesn't silently query the receiver on a schedule anyway.

    It can still be asked to refresh on demand (e.g. right after an
    action), just not automatically.
    """
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: False})
    calls_before = client.async_update_audyssey.await_count

    freezer.tick(timedelta(seconds=COORDINATOR_UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_update_audyssey.await_count == calls_before


async def test_setup_skips_redundant_audyssey_refresh_with_telnet(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Setup doesn't double-fetch Audyssey when Telnet already did.

    receiver.py's connection step already calls async_update_audyssey()
    for every zone when both Telnet and "Update Audyssey settings" are
    on - the coordinator's own initial refresh must not repeat that
    ~10s request on every setup or reload.
    """
    await setup_denonavr(
        hass, options={CONF_USE_TELNET: True, CONF_UPDATE_AUDYSSEY: True}
    )

    assert client.async_update_audyssey.await_count == 1


async def test_setup_forces_audyssey_fetch_with_telnet_but_no_polling(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Setup still fetches Audyssey once when Telnet is on but polling is off.

    Telnet only pushes Audyssey data on a change, never on connect, so
    without forcing this fetch, async_refresh_audyssey's own Telnet-
    healthy skip would leave these entities unavailable indefinitely -
    receiver.py didn't fetch it either, since that's gated on the
    polling option, not on Telnet being enabled.
    """
    client.telnet_connected = True
    client.telnet_healthy = True
    client.dynamic_eq = None
    client.reference_level_offset = None

    async def _populate(*_args: object, **_kwargs: object) -> None:
        client.dynamic_eq = True
        client.reference_level_offset = "0dB"

    client.async_update_audyssey.side_effect = _populate

    await setup_denonavr(
        hass, options={CONF_USE_TELNET: True, CONF_UPDATE_AUDYSSEY: False}
    )

    assert client.async_update_audyssey.await_count == 1
    entity_id = _entity_id(hass, "reference_level_offset")
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_refresh_failure_does_not_fail_an_already_successful_action(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A refresh failure must not fail an already-successful command.

    The user's requested change already applied; only the confirmation
    query failed, which should just leave the optimistic value in
    place rather than surface as an error.
    """
    await setup_denonavr(hass)
    entity_id = _entity_id(hass, "dimmer")

    client.async_update.side_effect = AvrCommandError("Timed out", "GetDimmer")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
        blocking=True,
    )

    client.async_dimmer.assert_awaited_once_with("Dark")
    assert hass.states.get(entity_id).state == "Dark"


async def test_rapid_consecutive_selections_do_not_race(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Two select_option calls fired back-to-back on the same entity must not race.

    The entity must end on the option selected last, not on whichever
    response landed last. PARALLEL_UPDATES only serializes calls targeting
    several entities at once, so this needs a lock of its own.
    """
    call_order = []

    async def _slow_dimmer_set(value):
        call_order.append(f"start-{value}")
        await asyncio.sleep(0.05)
        client.dimmer = value
        call_order.append(f"end-{value}")

    client.async_dimmer.side_effect = _slow_dimmer_set

    await setup_denonavr(hass)
    entity_id = _entity_id(hass, "dimmer")

    await asyncio.gather(
        hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
            blocking=True,
        ),
        hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dim"},
            blocking=True,
        ),
    )

    # Either call may win the lock; what must not happen is interleaving.
    assert call_order in (
        ["start-Dark", "end-Dark", "start-Dim", "end-Dim"],
        ["start-Dim", "end-Dim", "start-Dark", "end-Dark"],
    )
    # And the entity shows whichever option's set call actually finished
    # last - not a stale value from an overtaken earlier request.
    assert hass.states.get(entity_id).state == client.dimmer


async def test_telnet_notifies_audyssey_independently_of_media_player(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A Telnet callback notifying Audyssey listeners isn't tied to the entity.

    If it were only registered via the media_player entity's own
    async_added_to_hass, disabling that entity would stop it from
    firing - leaving these selects stale after Telnet updates even
    though the receiver itself keeps updating regardless.
    """
    await setup_denonavr(hass)
    entity_id = _entity_id(hass, "reference_level_offset")

    # Registered as a plain function, not a bound method of the
    # media_player entity - proving it doesn't depend on that entity
    # existing or being enabled.
    telnet_callbacks = [
        call.args[1]
        for call in client.register_callback.call_args_list
        if not hasattr(call.args[1], "__self__")
    ]
    assert telnet_callbacks

    client.dynamic_eq = False
    for callback in telnet_callbacks:
        callback("Main", "PS", "DYNEQ OFF")

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_audyssey_entities_not_unavailable_on_fresh_setup(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Audyssey-dependent entities aren't unavailable after a fresh setup.

    Nothing in the regular poll loop fetches Audyssey data unless
    "Update Audyssey settings" is on - without the one-time initial
    fetch, these entities (reference_level_offset especially, since it
    also gates on dynamic_eq) would stay unavailable indefinitely.
    """
    # Simulate a fresh receiver: nothing fetched yet.
    client.dynamic_eq = None
    client.reference_level_offset = None
    client.dynamic_volume = None
    client.multi_eq = None

    # Simulate what a real async_update_audyssey() call does: populate
    # the values, as if the device had just been queried.
    async def _populate_audyssey(*args, **kwargs):
        client.dynamic_eq = True
        client.reference_level_offset = "0dB"
        client.dynamic_volume = "Off"
        client.multi_eq = "Reference"

    client.async_update_audyssey.side_effect = _populate_audyssey

    # Option left at its documented default (off).
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: False})

    switch_entity_id = _entity_id(hass, "dynamic_eq", domain=SWITCH_DOMAIN)
    reflevoffset_entity_id = _entity_id(hass, "reference_level_offset")
    dynamic_volume_entity_id = _entity_id(hass, "dynamic_volume")
    multi_eq_entity_id = _entity_id(hass, "multi_eq")

    assert hass.states.get(switch_entity_id).state != "unavailable"
    assert hass.states.get(reflevoffset_entity_id).state != "unavailable"
    assert hass.states.get(dynamic_volume_entity_id).state != "unavailable"
    assert hass.states.get(multi_eq_entity_id).state != "unavailable"


async def test_option_shown_immediately_even_if_refresh_reads_back_stale_value(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A stale immediate refresh must not revert to the previous value."""
    # The refresh reports the old value, as if the command had not settled yet.
    client.async_update.side_effect = lambda *a, **k: None  # dimmer stays "Bright"

    await setup_denonavr(hass)
    entity_id = _entity_id(hass, "dimmer")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
        blocking=True,
    )
    # Let the debounced confirmation refresh run its stale read.
    await _wait_for_debounced_refresh(hass)

    client.async_dimmer.assert_awaited_once_with("Dark")
    assert hass.states.get(entity_id).state == "Dark"

    # Once the receiver catches up, the override reconciles instead of sticking.
    client.dimmer = "Dark"
    await async_update_entity(hass, entity_id)
    assert hass.states.get(entity_id).state == "Dark"


async def test_pending_option_expires_instead_of_masking_forever(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """The pending override must expire rather than mask reality forever.

    A command that silently did not apply, or an external change landing
    while a value is pending, leaves the receiver's value never catching
    up, and the override has to give way to it.
    """
    client.async_update.side_effect = lambda *a, **k: None  # dimmer stays "Bright"

    with patch("homeassistant.components.denonavr.entity.PENDING_VALUE_TIMEOUT", 0.01):
        await setup_denonavr(hass)
        entity_id = _entity_id(hass, "dimmer")

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
            blocking=True,
        )
        assert hass.states.get(entity_id).state == "Dark"

        # The front panel changes it to something else entirely while the
        # override is pending, and the patched 10ms timeout then runs out.
        client.dimmer = "Dim"
        await asyncio.sleep(0.02)
        await async_update_entity(hass, entity_id)

    assert hass.states.get(entity_id).state == "Dim"


async def test_pending_expiry_triggers_a_fresh_refresh(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Expiry alone should ask for one more read, not just show stale data.

    Without this, a command that was simply slow to actually apply (not
    lost or rejected) would be stuck showing the stale pre-command
    value forever, since nothing else would ever refresh it again.
    """
    with patch("homeassistant.components.denonavr.entity.PENDING_VALUE_TIMEOUT", 0.01):
        await setup_denonavr(hass)
        entity_id = _entity_id(hass, "dimmer")

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
            blocking=True,
        )
        await _wait_for_debounced_refresh(hass)
        calls_after_action = client.async_update.await_count

        # No manual poll or action here - expiry itself must be what
        # triggers the next read.
        await asyncio.sleep(0.02)
        await hass.async_block_till_done()

    assert client.async_update.await_count > calls_after_action


async def test_pending_expiry_reads_the_receiver_even_when_telnet_is_healthy(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Expiry is exactly the case where no Telnet push confirmed the value.

    An ordinary refresh skips the read while Telnet is healthy, which would
    leave expiry falling back to a cached value nothing ever corrects.
    """
    with patch("homeassistant.components.denonavr.entity.PENDING_VALUE_TIMEOUT", 0.01):
        await setup_denonavr(hass)
        client.telnet_connected = True
        client.telnet_healthy = True
        entity_id = _entity_id(hass, "dimmer")

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
            blocking=True,
        )
        await _wait_for_debounced_refresh(hass)
        calls_after_action = client.async_update.await_count

        await asyncio.sleep(0.02)
        await hass.async_block_till_done()

    assert client.async_update.await_count > calls_after_action


async def test_audyssey_poll_needs_an_entity_not_just_internal_wiring(
    hass: HomeAssistant, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """The cross-coordinator wiring alone must not keep the poll running.

    Loading no platforms leaves that wiring as the only subscriber, so a
    poll here would be one no entity ever asked for.
    """
    with patch("homeassistant.components.denonavr.PLATFORMS", []):
        await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: True})
        calls_before = client.async_update_audyssey.await_count

        freezer.tick(timedelta(seconds=COORDINATOR_UPDATE_INTERVAL + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert client.async_update_audyssey.await_count == calls_before


async def test_telnet_update_clears_an_audyssey_connectivity_failure(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A Telnet push has to restore availability, not only notify listeners.

    With "Update Audyssey settings" off this coordinator has no poll of
    its own, so notifying alone would leave these entities unavailable
    for as long as Telnet keeps them up to date.
    """
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: False})
    entity_id = _entity_id(hass, "multi_eq")

    client.async_set_multieq.side_effect = AvrNetworkError(
        "Connection refused", "SetAudyssey"
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Flat"},
            blocking=True,
        )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    telnet_callbacks = [
        call.args[1]
        for call in client.register_callback.call_args_list
        if not hasattr(call.args[1], "__self__")
    ]
    assert telnet_callbacks
    for telnet_callback in telnet_callbacks:
        telnet_callback("Main", "PS", "MULTEQ:AUDYSSEY")
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
