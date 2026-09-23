"""The tests for the denonavr media player platform."""

import asyncio
from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, create_autospec, patch

from denonavr import DenonAVR
from denonavr.const import POWER_ON
from denonavr.exceptions import (
    AvrCommandError,
    AvrIncompleteResponseError,
    AvrInvalidResponseError,
    AvrNetworkError,
    AvrProcessingError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import media_player
from homeassistant.components.denonavr.config_flow import (
    CONF_MANUFACTURER,
    CONF_SERIAL_NUMBER,
    CONF_TYPE,
    DOMAIN,
)
from homeassistant.components.denonavr.const import (
    ATTR_DYNAMIC_EQ,
    CONF_UPDATE_AUDYSSEY,
    CONF_USE_TELNET,
)
from homeassistant.components.denonavr.coordinator import mark_unavailable
from homeassistant.components.denonavr.services import (
    ATTR_COMMAND,
    SERVICE_GET_COMMAND,
    SERVICE_SET_DYNAMIC_EQ,
    SERVICE_UPDATE_AUDYSSEY,
)
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_MODEL,
    SERVICE_VOLUME_UP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_HOST = "1.2.3.4"
TEST_NAME = "Test_Receiver"
TEST_MODEL = "model5"
TEST_SERIALNUMBER = "123456789"
TEST_MANUFACTURER = "Denon"
TEST_RECEIVER_TYPE = "avr-x"
TEST_ZONE = "Main"
TEST_UNIQUE_ID = f"{TEST_MODEL}-{TEST_SERIALNUMBER}"
TEST_TIMEOUT = 2
TEST_SHOW_ALL_SOURCES = False
TEST_ZONE2 = False
TEST_ZONE3 = False
ENTITY_ID = f"{media_player.DOMAIN}.{TEST_NAME}"


@pytest.fixture(name="client")
def client_fixture() -> Generator[MagicMock]:
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
        mock_client_class.return_value.dynamic_eq = True
        yield mock_client_class.return_value


async def setup_denonavr(
    hass: HomeAssistant,
    serial_number: str | None = TEST_SERIALNUMBER,
    options: dict[str, bool] | None = None,
    pref_disable_polling: bool = False,
) -> MockConfigEntry:
    """Initialize media_player for tests."""
    entry_data = {
        CONF_HOST: TEST_HOST,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: serial_number,
    }

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID if serial_number else None,
        data=entry_data,
        options=options or {},
        pref_disable_polling=pref_disable_polling,
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == TEST_NAME

    return mock_entry


@pytest.mark.usefixtures("client")
async def test_setup_without_serial_number(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a receiver reporting no serial number still gets its media player."""
    entry = await setup_denonavr(hass, serial_number=None)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )


async def test_get_command(hass: HomeAssistant, client: MagicMock) -> None:
    """Test generic command functionality."""
    await setup_denonavr(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test_command",
    }
    await hass.services.async_call(DOMAIN, SERVICE_GET_COMMAND, data)
    await hass.async_block_till_done()

    client.async_get_command.assert_awaited_with("test_command")


async def test_update_entity_reads_before_returning(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test update_entity reads the receiver instead of only scheduling a read."""
    await setup_denonavr(hass)
    assert await async_setup_component(hass, "homeassistant", {})
    reads = client.async_update.await_count

    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert client.async_update.await_count > reads


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(
            AvrProcessingError("Update not complete", "SetVolume"), id="processing"
        ),
        pytest.param(
            AvrCommandError("Could not set volume", "SetVolume"), id="command"
        ),
    ],
)
async def test_non_connectivity_error_does_not_mark_unavailable(
    hass: HomeAssistant, client: MagicMock, exception: Exception
) -> None:
    """Not connectivity failures: the receiver answered, or rejected one command."""
    await setup_denonavr(hass)
    client.async_volume_up.side_effect = exception

    await hass.services.async_call(
        media_player.DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


async def test_queued_commands_warn_once_when_the_receiver_drops(
    hass: HomeAssistant, client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Queued commands each fail, but only the first warns.

    Both were dispatched while the entity was still available, so both run.
    """
    await setup_denonavr(hass)
    release = asyncio.Event()

    async def _fail_once_released() -> None:
        await release.wait()
        raise AvrNetworkError("Network error", "SetVolume")

    client.async_volume_up.side_effect = _fail_once_released
    calls = [
        hass.async_create_task(
            hass.services.async_call(
                media_player.DOMAIN,
                SERVICE_VOLUME_UP,
                {ATTR_ENTITY_ID: ENTITY_ID},
                blocking=True,
            )
        )
        for _ in range(2)
    ]
    release.set()
    await asyncio.gather(*calls)

    assert client.async_volume_up.await_count == 2
    assert caplog.text.count("Network error connecting") == 1


async def test_audyssey_command_failure_warns_with_polling_disabled(
    hass: HomeAssistant, client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """The first failure warns though the command already marked it unavailable.

    With polling disabled the Audyssey failure reaches the status coordinator
    before the decorator sees the exception.
    """
    await setup_denonavr(hass, pref_disable_polling=True)
    client.async_dynamic_eq_on.side_effect = AvrNetworkError(
        "Network error", "SetAudyssey"
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DYNAMIC_EQ,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_DYNAMIC_EQ: True},
        blocking=True,
    )

    assert caplog.text.count("Network error connecting") == 1


async def test_dynamic_eq_attribute_updates_from_audyssey_coordinator(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """The dynamic_eq attribute refreshes when the Audyssey coordinator does.

    CoordinatorEntity subscribes this entity to the general status
    coordinator alone, which is not the one that fetches Audyssey data.
    """
    entry = await setup_denonavr(hass)
    client.power = POWER_ON
    client.dynamic_eq = True
    entry.runtime_data.audyssey_coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_DYNAMIC_EQ] is True

    client.dynamic_eq = False
    entry.runtime_data.audyssey_coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_DYNAMIC_EQ] is False


async def test_set_dynamic_eq_connectivity_error_marks_audyssey_unavailable(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A connectivity failure here also affects the Audyssey coordinator.

    This command is Audyssey-scoped, sent directly to the receiver
    rather than through that coordinator - so on a connectivity
    failure, only marking the general coordinator unavailable (what
    the decorator already does) would leave Audyssey-backed entities
    still showing available with stale data.
    """
    entry = await setup_denonavr(hass)
    client.async_dynamic_eq_on.side_effect = AvrNetworkError(
        "Connection refused", "SetAudyssey"
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DYNAMIC_EQ,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_DYNAMIC_EQ: True},
    )
    await hass.async_block_till_done()

    assert entry.runtime_data.audyssey_coordinator.last_update_success is False


async def test_dynamic_eq(hass: HomeAssistant, client: MagicMock) -> None:
    """Test that dynamic eq method works."""
    await setup_denonavr(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_DYNAMIC_EQ: True,
    }
    # Verify on call
    await hass.services.async_call(DOMAIN, SERVICE_SET_DYNAMIC_EQ, data)
    await hass.async_block_till_done()

    # Verify off call
    data[ATTR_DYNAMIC_EQ] = False
    await hass.services.async_call(DOMAIN, SERVICE_SET_DYNAMIC_EQ, data)
    await hass.async_block_till_done()

    client.async_dynamic_eq_on.assert_called_once()
    client.async_dynamic_eq_off.assert_called_once()


@pytest.mark.parametrize(
    ("telnet_healthy", "options"),
    [
        pytest.param(False, {}, id="http"),
        pytest.param(True, {CONF_USE_TELNET: True}, id="telnet_healthy"),
    ],
)
async def test_update_audyssey(
    hass: HomeAssistant,
    client: MagicMock,
    telnet_healthy: bool,
    options: dict[str, bool],
) -> None:
    """The update_audyssey action fetches, even with Telnet healthy.

    The Telnet-healthy skip that saves scheduled polls an HTTP round-trip
    must not swallow this explicit one.
    """
    client.telnet_connected = client.telnet_healthy = telnet_healthy
    await setup_denonavr(hass, options=options)

    # Setup fetches this once too, so the assertion is on the one call the
    # service adds rather than on a fixed total.
    calls_before_service = client.async_update_audyssey.call_count

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_AUDYSSEY,
        {ATTR_ENTITY_ID: ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert client.async_update_audyssey.call_count == calls_before_service + 1


async def test_concurrent_forced_refreshes_share_one_bypassing_fetch(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Overlapping forced refreshes fetch once.

    Each would otherwise run the slow Audyssey query again behind the lock, or
    skip on a bypass flag the other had already cleared.
    """
    client.telnet_connected = True
    client.telnet_healthy = True
    entry = await setup_denonavr(
        hass, options={CONF_USE_TELNET: True, CONF_UPDATE_AUDYSSEY: True}
    )
    audyssey_coordinator = entry.runtime_data.audyssey_coordinator

    async def _suspending_update() -> None:
        # Yields so the second caller arrives while the first still
        # refreshes; without it the mock never suspends.
        await asyncio.sleep(0)

    client.async_update_audyssey.side_effect = _suspending_update
    calls_before = client.async_update_audyssey.call_count

    await asyncio.gather(
        audyssey_coordinator.async_refresh_forced(),
        audyssey_coordinator.async_refresh_forced(),
    )

    assert client.async_update_audyssey.call_count == calls_before + 1


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(None, STATE_UNKNOWN, id="status_answers"),
        pytest.param(
            AvrNetworkError("Network error", "test"),
            STATE_UNAVAILABLE,
            id="status_unreachable",
        ),
    ],
)
@pytest.mark.parametrize(
    "telnet_healthy_at_setup",
    [
        pytest.param(True, id="telnet_healthy"),
        # The status poll at setup read, and a coordinator judged by its last
        # read would keep counting on a poll that now skips.
        pytest.param(False, id="telnet_recovers_after_setup"),
    ],
)
async def test_initial_audyssey_failure_makes_the_status_poll_read(
    hass: HomeAssistant,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
    telnet_healthy_at_setup: bool,
    side_effect: Exception | None,
    expected_state: str,
) -> None:
    """A failed Audyssey fetch at setup makes the next status poll read.

    With Telnet healthy that poll would otherwise skip, never asking the
    receiver the Audyssey fetch just failed to reach. Its own read decides.
    """
    client.telnet_connected = True
    client.telnet_healthy = telnet_healthy_at_setup
    client.async_update_audyssey.side_effect = AvrNetworkError("Network error", "test")
    await setup_denonavr(hass, options={CONF_USE_TELNET: True})
    client.telnet_healthy = True
    client.async_update.side_effect = side_effect
    reads_before = client.async_update.await_count

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_update.await_count > reads_before
    assert hass.states.get(ENTITY_ID).state == expected_state


async def test_initial_audyssey_failure_reaches_a_status_coordinator_not_polling(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """With polling disabled for the entry, no poll of its own would find it."""
    client.async_update_audyssey.side_effect = AvrNetworkError("Network error", "test")

    await setup_denonavr(hass, pref_disable_polling=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(
            AvrProcessingError("Audyssey data not available"), id="processing"
        ),
        pytest.param(AvrNetworkError("Network error", "test"), id="network"),
    ],
)
@pytest.mark.parametrize(
    "options",
    [
        pytest.param({}, id="http"),
        pytest.param({CONF_UPDATE_AUDYSSEY: True}, id="http_audyssey"),
        pytest.param({CONF_USE_TELNET: True}, id="telnet"),
        pytest.param(
            {CONF_USE_TELNET: True, CONF_UPDATE_AUDYSSEY: True}, id="telnet_audyssey"
        ),
    ],
)
async def test_setup_survives_initial_audyssey_failure(
    hass: HomeAssistant,
    client: MagicMock,
    options: dict[str, bool],
    exception: Exception,
) -> None:
    """The setup-time Audyssey fetch must not keep the entry from loading.

    It runs in every configuration, on a receiver the connection step has
    already reached, so a failure leaves the Audyssey data unset instead of
    failing or retrying the whole entry.
    """
    client.telnet_connected = options.get(CONF_USE_TELNET, False)
    client.telnet_healthy = client.telnet_connected
    client.async_update_audyssey.side_effect = exception

    entry = await setup_denonavr(hass, options=options)

    assert entry.state is ConfigEntryState.LOADED
    # Forced, so the Telnet-healthy skip does not swallow it.
    client.async_update_audyssey.assert_awaited()


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(None, STATE_UNKNOWN, id="receiver_answers"),
        pytest.param(
            AvrNetworkError("Network error", "test"),
            STATE_UNAVAILABLE,
            id="still_unreachable",
        ),
    ],
)
async def test_unavailable_coordinator_reads_before_recovering(
    hass: HomeAssistant,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception | None,
    expected_state: str,
) -> None:
    """The Telnet-healthy skip must not be what clears a confirmed failure.

    A skipped poll reports success without asking the receiver, so it
    would restore availability with nothing behind it.
    """
    client.telnet_connected = True
    client.telnet_healthy = True
    entry = await setup_denonavr(hass, options={CONF_USE_TELNET: True})

    mark_unavailable(entry.runtime_data.coordinator)
    client.async_update.side_effect = side_effect
    reads_before = client.async_update.await_count

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_update.await_count > reads_before
    assert hass.states.get(ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    ("failing", "reading", "failing_method"),
    [
        pytest.param(
            "coordinator", "audyssey_coordinator", "async_update", id="status_fails"
        ),
        pytest.param(
            "audyssey_coordinator",
            "coordinator",
            "async_update_audyssey",
            id="audyssey_fails",
        ),
    ],
)
async def test_a_polling_coordinator_keeps_its_own_verdict(
    hass: HomeAssistant,
    client: MagicMock,
    failing: str,
    reading: str,
    failing_method: str,
) -> None:
    """A coordinator with its own poll is not handed the other one's failure.

    Both poll over HTTP here, so neither is guessing, and one endpoint
    refusing is no reason to hide data the receiver just answered for.
    """
    entry = await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: True})
    failing_coordinator = getattr(entry.runtime_data, failing)
    reading_coordinator = getattr(entry.runtime_data, reading)
    getattr(client, failing_method).side_effect = AvrNetworkError(
        "Network error", "test"
    )

    await failing_coordinator.async_refresh()

    assert failing_coordinator.last_update_success is False
    assert reading_coordinator.last_update_success is True


async def test_repeated_failure_still_reaches_a_coordinator_without_a_poll(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A failure that repeats must keep reaching a coordinator with no poll.

    DataUpdateCoordinator stops notifying listeners once a failure repeats, so
    a peer that went available in between would otherwise stay that way with
    no poll to check again. Audyssey has no recurring poll here.
    """
    entry = await setup_denonavr(hass)
    coordinator = entry.runtime_data.coordinator
    audyssey_coordinator = entry.runtime_data.audyssey_coordinator
    client.async_update.side_effect = AvrNetworkError("Network error", "test")

    await coordinator.async_refresh()

    assert audyssey_coordinator.last_update_success is False

    # Its own fetch answers, but it has no poll to keep confirming that.
    await audyssey_coordinator.async_refresh()

    assert audyssey_coordinator.last_update_success is True

    await coordinator.async_refresh()

    assert audyssey_coordinator.last_update_success is False


@pytest.mark.usefixtures("client")
async def test_repeated_command_failure_still_reaches_a_coordinator_without_a_poll(
    hass: HomeAssistant,
) -> None:
    """A second out-of-band failure must reach a peer that recovered since.

    With polling disabled for the entry no later read would hand it over, so
    the peer would stay available after the receiver failed again.
    """
    entry = await setup_denonavr(hass, pref_disable_polling=True)
    coordinator = entry.runtime_data.coordinator
    audyssey_coordinator = entry.runtime_data.audyssey_coordinator

    mark_unavailable(coordinator)

    assert audyssey_coordinator.last_update_success is False

    # A read of its own answers while the status coordinator is still down.
    await audyssey_coordinator.async_refresh()

    assert audyssey_coordinator.last_update_success is True

    mark_unavailable(coordinator)

    assert audyssey_coordinator.last_update_success is False


@pytest.mark.usefixtures("client")
async def test_update_audyssey_restores_availability(hass: HomeAssistant) -> None:
    """A successful call recovers Audyssey entities from a prior failure.

    The fetch is this zone's own rather than the coordinator's, so the
    coordinator has to be told it succeeded - otherwise a prior failure
    would keep every Audyssey-backed entity unavailable even after this
    has updated the receiver's properties.
    """
    entry = await setup_denonavr(hass)
    entry.runtime_data.audyssey_coordinator.last_update_success = False

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_AUDYSSEY,
        {ATTR_ENTITY_ID: ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert entry.runtime_data.audyssey_coordinator.last_update_success is True


async def test_update_audyssey_action_survives_a_receiver_without_audyssey(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """The action reads through the same tolerance the coordinator's refresh does.

    A receiver that answers the query short has no Audyssey, which is not a
    reason to raise at the caller or to hide the rest of its entities.
    """
    entry = await setup_denonavr(hass)
    client.async_update_audyssey.side_effect = AvrIncompleteResponseError(
        "Invalid length of response XML", "test"
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_AUDYSSEY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert entry.runtime_data.audyssey_coordinator.last_update_success is True
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


async def test_update_audyssey_fetches_only_the_targeted_zone(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """The action refreshes the zone it was called on, not every zone.

    It is an entity service, so targeting a receiver's zone media
    players calls it once per zone already - fetching every zone per
    call would square the number of these slow queries.
    """
    zone2 = create_autospec(DenonAVR, instance=True)
    zone2.name = TEST_NAME
    zone2.zone = "Zone2"
    zone2.input_func_list = []
    zone2.sound_mode_list = []
    client.zones = {TEST_ZONE: client, "Zone2": zone2}

    await setup_denonavr(hass)
    calls_before = zone2.async_update_audyssey.await_count

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_AUDYSSEY,
        {ATTR_ENTITY_ID: ENTITY_ID},
    )
    await hass.async_block_till_done()

    client.async_update_audyssey.assert_awaited()
    assert zone2.async_update_audyssey.await_count == calls_before


async def test_update_audyssey_connectivity_error_marks_media_player_unavailable(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A connectivity failure here also affects the general coordinator.

    This entity's own availability is tied to the general coordinator,
    not the Audyssey one it's routed through here - without also
    marking that one unavailable, a connectivity failure would leave
    this entity looking available despite just confirming the
    receiver itself is unreachable.
    """
    await setup_denonavr(hass)
    client.async_update_audyssey.side_effect = AvrNetworkError(
        "Connection refused", "GetAudyssey"
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_AUDYSSEY,
        {ATTR_ENTITY_ID: ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_set_dynamic_eq_always_refreshes_audyssey(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Refreshes Audyssey after this action regardless of the option.

    "Update Audyssey settings" only governs the recurring poll - this
    action just changed Audyssey-scoped data directly, and the
    dynamic_eq attribute it feeds has to reflect that either way.
    """
    with patch(
        "homeassistant.components.denonavr.coordinator.ACTION_REFRESH_DEBOUNCE_COOLDOWN",
        0,
    ):
        await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: False})
        calls_before = client.async_update_audyssey.await_count

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DYNAMIC_EQ,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_DYNAMIC_EQ: False},
        )
        await asyncio.sleep(0)
        await hass.async_block_till_done()

    assert client.async_update_audyssey.await_count > calls_before


async def test_update_audyssey_keeps_a_pending_audyssey_refresh(
    hass: HomeAssistant, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """The action's own fetch must not cancel the refresh set_dynamic_eq queued.

    Dynamic EQ is receiver-wide and Telnet never pushes the other zones'
    copies, so that refresh is what brings them in step. The real cooldown
    is needed: the action has to land inside it.
    """
    await setup_denonavr(hass)
    calls_before = client.async_update_audyssey.await_count

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DYNAMIC_EQ,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_DYNAMIC_EQ: False},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_AUDYSSEY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # One fetch from the action, one from the refresh it must not cancel.
    assert client.async_update_audyssey.await_count == calls_before + 2


async def test_setup_retry_on_request_error(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test that a failed request during setup retries the config entry."""
    client.async_update.side_effect = AvrInvalidResponseError(
        "Server disconnected without sending a response", "GET"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={
            CONF_HOST: TEST_HOST,
            CONF_MODEL: TEST_MODEL,
            CONF_TYPE: TEST_RECEIVER_TYPE,
            CONF_MANUFACTURER: TEST_MANUFACTURER,
            CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
        },
        options={CONF_USE_TELNET: True},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(
            AvrInvalidResponseError("XML parse error", "GET"),
            id="invalid_response",
        ),
        pytest.param(
            AvrIncompleteResponseError("Incomplete", "GET"),
            id="incomplete_response",
        ),
    ],
)
async def test_malformed_response_marks_unavailable(
    hass: HomeAssistant,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that malformed response errors mark the entity unavailable."""
    await setup_denonavr(hass)

    state = hass.states.get(ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Force polling by disabling telnet, then trigger the error
    client.telnet_connected = False
    client.telnet_healthy = False
    client.async_update.side_effect = exception
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE
