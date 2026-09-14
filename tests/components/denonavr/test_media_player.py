"""The tests for the denonavr media player platform."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from denonavr.const import POWER_ON
from denonavr.exceptions import (
    AvrIncompleteResponseError,
    AvrInvalidResponseError,
    AvrNetworkError,
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
from homeassistant.components.denonavr.const import ATTR_DYNAMIC_EQ
from homeassistant.components.denonavr.services import (
    ATTR_COMMAND,
    SERVICE_GET_COMMAND,
    SERVICE_SET_DYNAMIC_EQ,
    SERVICE_UPDATE_AUDYSSEY,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_MODEL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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
        # Not used by these tests directly, but select/switch are set
        # up alongside media_player in every test here too (the same
        # config entry forwards all platforms) - leaving these as
        # auto-generated MagicMocks makes the entity registry's stored
        # "capabilities.options" for those selects an unserializable
        # mock, which crashes the whole test's teardown when it tries
        # to write the registry, not just something scoped to
        # media_player. See the matching comment in test_switch.py.
        mock_client_class.return_value.dynamic_eq = True
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
    hass: HomeAssistant,
    serial_number: str | None = TEST_SERIALNUMBER,
    options: dict | None = None,
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


async def test_dynamic_eq_attribute_updates_from_audyssey_coordinator(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """The dynamic_eq attribute refreshes when the Audyssey coordinator does.

    It's Audyssey-scoped data, but this entity's own coordinator
    subscription (from CoordinatorEntity) only covers general status -
    without a separate subscription to the Audyssey coordinator too,
    a switch toggle, the update/set services, or a periodic Audyssey
    refresh would leave this attribute stale until something unrelated
    (e.g. Telnet or the next general poll) happened to rewrite state.
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


async def test_update_audyssey(hass: HomeAssistant, client: MagicMock) -> None:
    """Test that dynamic eq method works."""
    await setup_denonavr(hass)

    # The Audyssey coordinator also fetches this once at setup (see
    # homeassistant/components/denonavr/coordinator.py), so the mock
    # has already been called by the time the service below runs -
    # assert the service adds exactly one more call, rather than a
    # fixed total.
    calls_before_service = client.async_update_audyssey.call_count

    # Verify call
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_AUDYSSEY,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
        },
    )
    await hass.async_block_till_done()

    assert client.async_update_audyssey.call_count == calls_before_service + 1


async def test_update_audyssey_restores_availability(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """A successful call recovers Audyssey entities from a prior failure.

    Calling the receiver directly instead of going through the
    coordinator would change its properties without updating the
    Audyssey coordinator's last_update_success, so a prior failure
    would keep every Audyssey-backed entity unavailable even after
    this succeeds.
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
    entry = await setup_denonavr(hass)
    client.async_update_audyssey.side_effect = AvrNetworkError(
        "Connection refused", "GetAudyssey"
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_AUDYSSEY,
        {ATTR_ENTITY_ID: ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert entry.runtime_data.coordinator.last_update_success is False


async def test_set_dynamic_eq_always_refreshes_audyssey(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Refreshes Audyssey after this action regardless of the option.

    "Update Audyssey settings" only governs the recurring poll - this
    action just changed Audyssey-scoped data directly, so the new
    select/switch entities need to hear about it either way.
    """
    with patch(
        "homeassistant.components.denonavr.coordinator.ACTION_REFRESH_DEBOUNCE_COOLDOWN",
        0,
    ):
        await setup_denonavr(hass, options={"update_audyssey": False})
        calls_before = client.async_update_audyssey.await_count

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DYNAMIC_EQ,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_DYNAMIC_EQ: False},
        )
        await asyncio.sleep(0)
        await hass.async_block_till_done()

    assert client.async_update_audyssey.await_count > calls_before


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
