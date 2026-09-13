"""The tests for the denonavr select platform."""

import asyncio
from unittest.mock import MagicMock, patch

from denonavr.exceptions import AvrCommandError
import pytest
from homeassistant.components.denonavr.config_flow import (
    CONF_MANUFACTURER,
    CONF_SERIAL_NUMBER,
    CONF_TYPE,
    DOMAIN,
)
from homeassistant.components.denonavr.const import CONF_UPDATE_AUDYSSEY
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    CONF_HOST,
    CONF_MODEL,
    SERVICE_SELECT_OPTION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_NAME = "Test_Receiver"
TEST_MODEL = "model5"
TEST_SERIALNUMBER = "123456789"
TEST_MANUFACTURER = "Denon"
TEST_RECEIVER_TYPE = "avr-x"
TEST_ZONE = "Main"
TEST_UNIQUE_ID = f"{TEST_MODEL}-{TEST_SERIALNUMBER}"


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


async def test_dimmer_refreshes_and_shows_new_state_immediately(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test that a stale immediate refresh doesn't revert a just-set value."""

    async def _apply_dimmer_change(*args, **kwargs):
        client.dimmer = "Dark"

    # side_effect must be the async function itself (not a sync lambda
    # that merely returns a coroutine) - AsyncMock only awaits side_effect
    # automatically when it's a coroutine function; a sync wrapper just
    # creates an un-awaited coroutine that never actually runs.
    client.async_update.side_effect = _apply_dimmer_change

    await setup_denonavr(hass)
    entity_id = _entity_id(hass, "dimmer")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
        blocking=True,
    )

    # The refresh call happened (our own explicit one, plus HA's own
    # built-in post-service-call poll for should_poll=True entities)...
    assert client.async_update.await_count == 2
    # ...and the new value is visible right away, with no time-based
    # polling trick needed to observe it.
    assert hass.states.get(entity_id).state == "Dark"


async def test_eco_mode_and_auto_standby_also_refresh_immediately(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Same fix, the other two plain-appcommand settings."""
    await setup_denonavr(hass)

    eco_entity_id = _entity_id(hass, "eco_mode")
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: eco_entity_id, ATTR_OPTION: "Off"},
        blocking=True,
    )
    client.async_update.assert_awaited()

    standby_entity_id = _entity_id(hass, "auto_standby")
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: standby_entity_id, ATTR_OPTION: "15M"},
        blocking=True,
    )
    # Two calls per action (our own explicit refresh plus HA's built-in
    # post-service-call poll for should_poll=True entities).
    assert client.async_update.await_count == 4


async def test_reference_level_offset_always_refreshes_after_change(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Audyssey-group settings always force-refresh after a change.

    Regardless of the (separate, poll-loop-only) "Update Audyssey
    settings" option. Gating this refresh on that option - which is off
    by default - meant the receiver applied the change correctly but
    the UI never showed it, since Audyssey values aren't otherwise
    fetched by the regular poll loop at all.
    """
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: False})
    entity_id = _entity_id(hass, "reference_level_offset")

    # Setup itself does one initial Audyssey fetch per platform (select
    # + switch), so both entities start with a real value instead of
    # "unavailable".
    baseline_calls = client.async_update_audyssey.await_count

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "+5dB"},
        blocking=True,
    )
    # Just one call: our own explicit refresh (unconditional). HA's
    # built-in post-service-call poll would add a second, but that one
    # now correctly respects "Update Audyssey settings" (off here), so
    # it's skipped rather than firing regardless like the explicit one.
    assert client.async_update_audyssey.await_count == baseline_calls + 1


async def test_reference_level_offset_poll_refresh_respects_audyssey_option(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """The recurring poll honors the "Update Audyssey settings" option.

    Matches the existing precedent for media_player.py's own recurring
    poll - unlike the post-change refresh, which stays unconditional
    regardless.
    """
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: True})
    entity_id = _entity_id(hass, "reference_level_offset")

    baseline_calls = client.async_update_audyssey.await_count
    await async_update_entity(hass, entity_id)
    assert client.async_update_audyssey.await_count == baseline_calls + 1


async def test_reference_level_offset_poll_refresh_skipped_when_option_off(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """The recurring poll is skipped, not just left unconfirmed, when off.

    Confirms it doesn't silently query the receiver anyway.
    """
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: False})
    entity_id = _entity_id(hass, "reference_level_offset")

    baseline_calls = client.async_update_audyssey.await_count
    await async_update_entity(hass, entity_id)
    assert client.async_update_audyssey.await_count == baseline_calls


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

    Whichever finishes last should reflect the option that was
    *actually* selected last, not whichever request's response
    happened to land last. A per-entity lock is required for this -
    HA's PARALLEL_UPDATES only serializes service calls that target
    multiple entities at once, not repeated calls each targeting this
    one entity.
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

    # Serialized: one call fully completes (start+end) before the next
    # one starts. Interleaved (start-A, start-B, end-A, end-B) would
    # mean they raced.
    assert call_order in (
        ["start-Dark", "end-Dark", "start-Dim", "end-Dim"],
        ["start-Dim", "end-Dim", "start-Dark", "end-Dark"],
    )
    # And the entity shows whichever option's set call actually finished
    # last - not a stale value from an overtaken earlier request.
    assert hass.states.get(entity_id).state == client.dimmer


async def test_audyssey_entities_not_unavailable_on_fresh_setup(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Reproduces the reported bug: a fresh integration load starts unavailable.

    On a fresh integration load, the library hasn't fetched Audyssey
    data yet (dynamic_eq/reflevoffset/dynamic_volume/multi_eq all start
    as None), and nothing in the regular poll loop ever fetches them
    unless "Update Audyssey settings" is on. Without the one-time
    initial fetch, every Audyssey-dependent entity would be permanently
    unavailable from the moment it's created - reference_level_offset
    especially, since it also gates on dynamic_eq being true.
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
    # dimmer starts "Bright"; simulate the receiver's refresh call
    # responding with the *old* value, as if the command hadn't
    # internally settled yet by the time we queried it.
    client.async_update.side_effect = lambda *a, **k: None  # dimmer stays "Bright"

    await setup_denonavr(hass)
    entity_id = _entity_id(hass, "dimmer")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Dark"},
        blocking=True,
    )

    # The command was sent...
    client.async_dimmer.assert_awaited_once_with("Dark")
    # ...and even though the immediate refresh read back the stale
    # "Bright", the UI shows what was actually picked, not what the
    # receiver momentarily still reported.
    assert hass.states.get(entity_id).state == "Dark"

    # Once the receiver's value genuinely catches up (e.g. on a later,
    # unrelated poll that happens to refresh it - simulated directly
    # here), the override reconciles cleanly rather than getting stuck.
    client.dimmer = "Dark"
    await async_update_entity(hass, entity_id)
    assert hass.states.get(entity_id).state == "Dark"


async def test_pending_option_expires_instead_of_masking_forever(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """The pending override must expire rather than mask reality forever.

    If the receiver's value never actually catches up to what was set
    (a command that silently didn't apply, or a genuinely different
    external change landing while a value is pending), the override
    must not mask reality forever - it should expire and let the
    receiver's real value show through again.
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

        # Someone changes it via the physical remote to something else
        # entirely while our override is still pending, and enough time
        # passes (the patched timeout above is 10ms) that the override
        # should no longer be trusted.
        client.dimmer = "Dim"
        await asyncio.sleep(0.02)
        await async_update_entity(hass, entity_id)

    assert hass.states.get(entity_id).state == "Dim"
