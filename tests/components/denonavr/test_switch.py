"""The tests for the denonavr switch platform."""

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
from homeassistant.components.denonavr.switch import DYNAMIC_EQ_DESCRIPTION
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_MODEL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
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
SWITCH_ENTITY_ID = f"{SWITCH_DOMAIN}.{TEST_NAME.lower()}_dynamic_eq"


@pytest.fixture(autouse=True)
def _fast_action_refresh_debounce():
    """Patch the action-refresh debounce cooldown down for every test.

    See the matching fixture/comment in test_select.py.
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
        mock_client_class.return_value.dynamic_eq = True
        # Not used by these tests directly, but the select platform is
        # set up alongside switch in every test here too (the same
        # config entry forwards all platforms) - leaving these as
        # auto-generated MagicMocks makes the entity registry's stored
        # "capabilities.options" for those selects an unserializable
        # mock, which crashes the whole test's teardown when it tries
        # to write the registry, not just something scoped to switch.
        mock_client_class.return_value.reference_level_offset_setting_list = [
            "0dB",
            "+5dB",
            "+10dB",
            "+15dB",
        ]
        mock_client_class.return_value.dynamic_volume_setting_list = [
            "Off",
            "Light",
            "Medium",
            "Heavy",
        ]
        mock_client_class.return_value.multi_eq_setting_list = [
            "Off",
            "Flat",
            "L/R Bypass",
            "Reference",
            "Manual",
        ]
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

    See the matching helper/comment in test_select.py.
    """
    await asyncio.sleep(0)
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, domain: str, key: str) -> str:
    """Look up an entity_id by its unique_id suffix."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{TEST_UNIQUE_ID}-{key}")
    assert entity_id is not None
    return entity_id


async def test_has_a_fallback_name_if_translation_lookup_fails() -> None:
    """Its description has a name and a translation_key for fallback."""
    assert DYNAMIC_EQ_DESCRIPTION.name == "Dynamic EQ"
    assert DYNAMIC_EQ_DESCRIPTION.translation_key == "dynamic_eq"


async def test_dynamic_eq_state_on(hass: HomeAssistant, client: MagicMock) -> None:
    """Test the switch reports on when Dynamic EQ is on."""
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"


async def test_dynamic_eq_unavailable_when_unknown(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the switch is unavailable when the receiver reports no Dynamic EQ state."""
    client.dynamic_eq = None
    await setup_denonavr(hass)

    entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_turn_on_dynamic_eq(hass: HomeAssistant, client: MagicMock) -> None:
    """Test turning Dynamic EQ on."""
    await setup_denonavr(hass)
    entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    client.async_dynamic_eq_on.assert_awaited_once()


async def test_turn_off_dynamic_eq(hass: HomeAssistant, client: MagicMock) -> None:
    """Test turning Dynamic EQ off."""
    await setup_denonavr(hass)
    entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    client.async_dynamic_eq_off.assert_awaited_once()


async def test_turn_on_raises_on_avr_error(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test that a receiver error while toggling is surfaced to the user."""
    await setup_denonavr(hass)
    entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")

    client.async_dynamic_eq_on.side_effect = AvrCommandError(
        "Could not set DynamicEQ", "SetAudyssey"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_reference_level_offset_agrees_with_switch_at_setup(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Select and switch agree on Dynamic EQ state at setup time.

    Both read the same receiver.dynamic_eq property, so they can't
    disagree about the value they were set up with. See
    test_toggling_switch_updates_dependent_select for what happens on
    a live toggle afterward.
    """
    client.reference_level_offset = "0dB"
    client.reference_level_offset_setting_list = ["0dB", "+5dB", "+10dB", "+15dB"]
    client.dynamic_volume = "Off"
    client.dynamic_volume_setting_list = ["Off", "Light", "Medium", "Heavy"]
    client.multi_eq = "Reference"
    client.multi_eq_setting_list = ["Off", "Flat", "L/R Bypass", "Reference", "Manual"]
    client.eco_mode = "Auto"
    client.dimmer = "Bright"
    client.auto_standby = "OFF"

    # Dynamic EQ on at setup -> both entities agree it's usable.
    client.dynamic_eq = True
    await setup_denonavr(hass)

    reflevoffset_entity_id = _entity_id(hass, SELECT_DOMAIN, "reference_level_offset")
    switch_entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")

    assert hass.states.get(switch_entity_id).state == "on"
    assert hass.states.get(reflevoffset_entity_id).state != STATE_UNAVAILABLE


async def test_reference_level_offset_unavailable_at_setup_when_dynamic_eq_off(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Same cross-check, the other way around.

    Dynamic EQ off at setup means both the switch reports off and the
    select is immediately unavailable - there's no window where they
    could disagree, since they share the same underlying
    receiver.dynamic_eq read.
    """
    client.reference_level_offset = "0dB"
    client.reference_level_offset_setting_list = ["0dB", "+5dB", "+10dB", "+15dB"]
    client.dynamic_volume = "Off"
    client.dynamic_volume_setting_list = ["Off", "Light", "Medium", "Heavy"]
    client.multi_eq = "Reference"
    client.multi_eq_setting_list = ["Off", "Flat", "L/R Bypass", "Reference", "Manual"]
    client.eco_mode = "Auto"
    client.dimmer = "Bright"
    client.auto_standby = "OFF"

    client.dynamic_eq = False
    await setup_denonavr(hass)

    reflevoffset_entity_id = _entity_id(hass, SELECT_DOMAIN, "reference_level_offset")
    switch_entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")

    assert hass.states.get(switch_entity_id).state == "off"
    assert hass.states.get(reflevoffset_entity_id).state == STATE_UNAVAILABLE


async def test_toggling_switch_updates_dependent_select(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Toggling Dynamic EQ off also updates Reference Level Offset.

    Both entities share the same Audyssey coordinator, so refreshing
    after the switch's own action notifies every entity subscribed to
    it, not just the switch itself.
    """
    client.reference_level_offset = "0dB"
    client.reference_level_offset_setting_list = ["0dB", "+5dB", "+10dB", "+15dB"]
    client.dynamic_volume = "Off"
    client.dynamic_volume_setting_list = ["Off", "Light", "Medium", "Heavy"]
    client.multi_eq = "Reference"
    client.multi_eq_setting_list = ["Off", "Flat", "L/R Bypass", "Reference", "Manual"]
    client.eco_mode = "Auto"
    client.dimmer = "Bright"
    client.auto_standby = "OFF"
    client.dynamic_eq = True

    await setup_denonavr(hass)

    reflevoffset_entity_id = _entity_id(hass, SELECT_DOMAIN, "reference_level_offset")
    switch_entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")
    assert hass.states.get(reflevoffset_entity_id).state != STATE_UNAVAILABLE

    async def _turn_off(*args, **kwargs):
        client.dynamic_eq = False

    client.async_dynamic_eq_off.side_effect = _turn_off

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: switch_entity_id},
        blocking=True,
    )
    await _wait_for_debounced_refresh(hass)

    # The switch itself updates...
    assert hass.states.get(switch_entity_id).state == "off"
    # ...and so does the select, from the very same refresh - no
    # separate poll or explicit cross-notification needed.
    assert hass.states.get(reflevoffset_entity_id).state == STATE_UNAVAILABLE


async def test_turn_on_shows_state_immediately_without_polling(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the switch reflects the new state right after the call.

    Not only once its own independent poll cycle happens to fire -
    this is the same class of bug reported for the Dimmer select
    entity.
    """
    client.dynamic_eq = False
    await setup_denonavr(hass)
    entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")
    assert hass.states.get(entity_id).state == "off"

    async def _turn_on(*args, **kwargs):
        client.dynamic_eq = True

    client.async_dynamic_eq_on.side_effect = _turn_on

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    # No freezer/async_fire_time_changed needed - the state must already
    # be correct as soon as the service call returns.
    assert hass.states.get(entity_id).state == "on"


async def test_turn_on_always_refreshes_audyssey_after_change(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Dynamic EQ refreshes Audyssey data regardless of the "Update Audyssey settings" option (see select.py for why)."""
    await setup_denonavr(hass, options={CONF_UPDATE_AUDYSSEY: False})
    entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")

    # Setup already does one initial Audyssey fetch.
    baseline_calls = client.async_update_audyssey.await_count

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await _wait_for_debounced_refresh(hass)

    # Just one call, since this is the only entity acting - HA's own
    # post-service-call poll doesn't apply here (should_poll=False).
    assert client.async_update_audyssey.await_count == baseline_calls + 1


async def test_rapid_toggles_do_not_race(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Two turn_on/turn_off calls fired back-to-back must not race.

    See the matching select.py test for why PARALLEL_UPDATES alone
    isn't enough here.
    """
    call_order = []

    async def _slow_on(*args, **kwargs):
        call_order.append("start-on")
        await asyncio.sleep(0.05)
        client.dynamic_eq = True
        call_order.append("end-on")

    async def _slow_off(*args, **kwargs):
        call_order.append("start-off")
        await asyncio.sleep(0.05)
        client.dynamic_eq = False
        call_order.append("end-off")

    client.async_dynamic_eq_on.side_effect = _slow_on
    client.async_dynamic_eq_off.side_effect = _slow_off

    await setup_denonavr(hass)
    entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")

    await asyncio.gather(
        hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        ),
        hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        ),
    )

    assert call_order in (
        ["start-on", "end-on", "start-off", "end-off"],
        ["start-off", "end-off", "start-on", "end-on"],
    )
    expected_state = "on" if client.dynamic_eq else "off"
    assert hass.states.get(entity_id).state == expected_state


async def test_state_shown_immediately_even_if_refresh_reads_back_stale_value(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A stale immediate refresh must not revert a just-set state."""
    # Simulate the receiver's Audyssey refresh responding with the old
    # value, as if the command hadn't internally settled yet.
    client.async_update_audyssey.side_effect = lambda *a, **k: None  # stays True

    await setup_denonavr(hass)
    entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    client.async_dynamic_eq_off.assert_awaited_once()
    assert hass.states.get(entity_id).state == "off"


async def test_pending_state_expires_instead_of_masking_forever(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A pending state must expire rather than mask reality forever."""
    client.async_update_audyssey.side_effect = lambda *a, **k: None  # stays True

    with patch("homeassistant.components.denonavr.entity.PENDING_VALUE_TIMEOUT", 0.01):
        await setup_denonavr(hass)
        entity_id = _entity_id(hass, SWITCH_DOMAIN, "dynamic_eq")

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        assert hass.states.get(entity_id).state == "off"

        # Receiver actually ends up "on" via some other path, and enough
        # time passes (the patched timeout above is 10ms) that the
        # override should no longer be trusted.
        client.dynamic_eq = True
        await asyncio.sleep(0.02)
        await async_update_entity(hass, entity_id)

        assert hass.states.get(entity_id).state == "on"
