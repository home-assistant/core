"""Tests for the PS4 media player platform."""
from pyps4_2ndscreen.credential import get_ddp_message

from homeassistant.components import ps4
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    MEDIA_TYPE_GAME,
)
from homeassistant.components.ps4.const import (
    ATTR_MEDIA_IMAGE_URL,
    CONFIG_ENTRY_VERSION as VERSION,
    DEFAULT_PORT,
    DEFAULT_REGION,
    DOMAIN,
    GAMES_FILE,
    PS4_DATA,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    ATTR_LOCKED,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_REGION,
    CONF_TOKEN,
    STATE_IDLE,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNKNOWN,
)
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry, mock_device_registry, mock_registry

MOCK_CREDS = "123412341234abcd12341234abcd12341234abcd12341234abcd12341234abcd"
MOCK_NAME = "ha_ps4_name"
MOCK_REGION = DEFAULT_REGION
MOCK_GAMES_FILE = GAMES_FILE
MOCK_HOST = "192.168.0.2"
MOCK_HOST_NAME = "Fake PS4"
MOCK_HOST_ID = "A0000A0AA000"
MOCK_HOST_VERSION = "09879011"
MOCK_HOST_TYPE = "PS4"
MOCK_STATUS_REST = "Server Standby"
MOCK_STATUS_ON = "Ok"
MOCK_STANDBY_CODE = 620
MOCK_ON_CODE = 200
MOCK_OPTIONS_PORT = 9870
MOCK_OPTIONS_PORT_2 = 9871
MOCK_TCP_PORT = 997
MOCK_DDP_PORT = 987
MOCK_DDP_VERSION = "00020020"
MOCK_RANDOM_PORT = "1234"

MOCK_TITLE_ID = "CUSA00000"
MOCK_TITLE_NAME = "Random Game"
MOCK_TITLE_TYPE = MEDIA_TYPE_GAME
MOCK_TITLE_ART_URL = "https://somecoverurl"

MOCK_GAMES_DATA = {
    ATTR_LOCKED: False,
    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_GAME,
    ATTR_MEDIA_IMAGE_URL: MOCK_TITLE_ART_URL,
    ATTR_MEDIA_TITLE: MOCK_TITLE_NAME,
}

MOCK_GAMES_DATA_LOCKED = {
    ATTR_LOCKED: True,
    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_GAME,
    ATTR_MEDIA_IMAGE_URL: MOCK_TITLE_ART_URL,
    ATTR_MEDIA_TITLE: MOCK_TITLE_NAME,
}

MOCK_STATUS_PLAYING = {
    "host-type": MOCK_HOST_TYPE,
    "host-ip": MOCK_HOST,
    "host-request-port": MOCK_TCP_PORT,
    "host-id": MOCK_HOST_ID,
    "host-name": MOCK_HOST_NAME,
    "running-app-titleid": MOCK_TITLE_ID,
    "running-app-name": MOCK_TITLE_NAME,
    "status": MOCK_STATUS_ON,
    "status_code": MOCK_ON_CODE,
    "device-discovery-protocol-version": MOCK_DDP_VERSION,
    "system-version": MOCK_HOST_VERSION,
}

MOCK_STATUS_IDLE = {
    "host-type": MOCK_HOST_TYPE,
    "host-ip": MOCK_HOST,
    "host-request-port": MOCK_TCP_PORT,
    "host-id": MOCK_HOST_ID,
    "host-name": MOCK_HOST_NAME,
    "status": MOCK_STATUS_ON,
    "status_code": MOCK_ON_CODE,
    "device-discovery-protocol-version": MOCK_DDP_VERSION,
    "system-version": MOCK_HOST_VERSION,
}

MOCK_STATUS_STANDBY = {
    "host-type": MOCK_HOST_TYPE,
    "host-ip": MOCK_HOST,
    "host-request-port": MOCK_TCP_PORT,
    "host-id": MOCK_HOST_ID,
    "host-name": MOCK_HOST_NAME,
    "status": MOCK_STATUS_REST,
    "status_code": MOCK_STANDBY_CODE,
    "device-discovery-protocol-version": MOCK_DDP_VERSION,
    "system-version": MOCK_HOST_VERSION,
}

MOCK_DEVICE = {CONF_HOST: MOCK_HOST, CONF_NAME: MOCK_NAME, CONF_REGION: MOCK_REGION}

MOCK_ENTRY_ID = "SomeID"

MOCK_DEVICE_MODEL = "PlayStation 4"

MOCK_DATA = {CONF_TOKEN: MOCK_CREDS, "devices": [MOCK_DEVICE]}

MOCK_CONFIG = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA, entry_id=MOCK_ENTRY_ID)

MOCK_LOAD = "homeassistant.components.ps4.media_player.load_games"


async def setup_mock_component(hass, entry=None):
    """Set up Mock Media Player."""
    if entry is None:
        mock_entry = MockConfigEntry(
            domain=ps4.DOMAIN, data=MOCK_DATA, version=VERSION, entry_id=MOCK_ENTRY_ID
        )
    else:
        mock_entry = entry

    mock_entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    await hass.async_block_till_done()

    mock_entities = hass.states.async_entity_ids()

    mock_entity_id = mock_entities[0]

    return mock_entity_id


async def mock_ddp_response(hass, mock_status_data):
    """Mock raw UDP response from device."""
    mock_protocol = hass.data[PS4_DATA].protocol

    mock_code = mock_status_data.get("status_code")
    mock_status = mock_status_data.get("status")
    mock_status_header = f"{mock_code} {mock_status}"
    mock_response = get_ddp_message(mock_status_header, mock_status_data).encode()

    mock_protocol.datagram_received(mock_response, (MOCK_HOST, MOCK_RANDOM_PORT))
    await hass.async_block_till_done()


async def test_media_player_is_setup_correctly_with_entry(hass):
    """Test entity is setup correctly with entry correctly."""
    mock_entity_id = await setup_mock_component(hass)
    mock_state = hass.states.get(mock_entity_id).state

    # Assert status updated callback is added to protocol.
    assert len(hass.data[PS4_DATA].protocol.callbacks) == 1

    # Test that entity is added to hass.
    assert hass.data[PS4_DATA].protocol is not None
    assert mock_entity_id == f"media_player.{MOCK_NAME}"
    assert mock_state == STATE_UNKNOWN


async def test_state_standby_is_set(hass):
    """Test that state is set to standby."""
    mock_entity_id = await setup_mock_component(hass)

    await mock_ddp_response(hass, MOCK_STATUS_STANDBY)

    assert hass.states.get(mock_entity_id).state == STATE_STANDBY


async def test_state_playing_is_set(hass):
    """Test that state is set to playing."""
    mock_entity_id = await setup_mock_component(hass)
    mock_func = "{}{}".format(
        "homeassistant.components.ps4.media_player.",
        "pyps4.Ps4Async.async_get_ps_store_data",
    )

    with patch(mock_func, return_value=None):
        await mock_ddp_response(hass, MOCK_STATUS_PLAYING)

    assert hass.states.get(mock_entity_id).state == STATE_PLAYING


async def test_state_idle_is_set(hass):
    """Test that state is set to idle."""
    mock_entity_id = await setup_mock_component(hass)

    await mock_ddp_response(hass, MOCK_STATUS_IDLE)

    assert hass.states.get(mock_entity_id).state == STATE_IDLE


async def test_state_none_is_set(hass):
    """Test that state is set to None."""
    mock_entity_id = await setup_mock_component(hass)

    assert hass.states.get(mock_entity_id).state == STATE_UNKNOWN


async def test_media_attributes_are_fetched(hass):
    """Test that media attributes are fetched."""
    mock_entity_id = await setup_mock_component(hass)
    mock_func = "{}{}".format(
        "homeassistant.components.ps4.media_player.",
        "pyps4.Ps4Async.async_get_ps_store_data",
    )

    # Mock result from fetching data.
    mock_result = MagicMock()
    mock_result.name = MOCK_TITLE_NAME
    mock_result.cover_art = MOCK_TITLE_ART_URL
    mock_result.game_type = "game"

    with patch(mock_func, return_value=mock_result) as mock_fetch:
        await mock_ddp_response(hass, MOCK_STATUS_PLAYING)

    mock_state = hass.states.get(mock_entity_id)
    mock_attrs = dict(mock_state.attributes)

    assert len(mock_fetch.mock_calls) == 1

    assert mock_state.state == STATE_PLAYING
    assert len(mock_attrs.get(ATTR_INPUT_SOURCE_LIST)) == 1
    assert mock_attrs.get(ATTR_INPUT_SOURCE_LIST)[0] == MOCK_TITLE_NAME
    assert mock_attrs.get(ATTR_MEDIA_CONTENT_ID) == MOCK_TITLE_ID
    assert mock_attrs.get(ATTR_MEDIA_TITLE) == MOCK_TITLE_NAME
    assert mock_attrs.get(ATTR_MEDIA_CONTENT_TYPE) == MOCK_TITLE_TYPE


async def test_media_attributes_are_loaded(hass, patch_load_json):
    """Test that media attributes are loaded."""
    mock_entity_id = await setup_mock_component(hass)
    patch_load_json.return_value = {MOCK_TITLE_ID: MOCK_GAMES_DATA_LOCKED}

    with patch(
        "homeassistant.components.ps4.media_player."
        "pyps4.Ps4Async.async_get_ps_store_data",
        return_value=None,
    ) as mock_fetch:
        await mock_ddp_response(hass, MOCK_STATUS_PLAYING)

    mock_state = hass.states.get(mock_entity_id)
    mock_attrs = dict(mock_state.attributes)

    # Ensure that data is not fetched.
    assert not mock_fetch.mock_calls

    assert mock_state.state == STATE_PLAYING

    assert len(mock_attrs.get(ATTR_INPUT_SOURCE_LIST)) == 1
    assert mock_attrs.get(ATTR_INPUT_SOURCE_LIST)[0] == MOCK_TITLE_NAME
    assert mock_attrs.get(ATTR_MEDIA_CONTENT_ID) == MOCK_TITLE_ID
    assert mock_attrs.get(ATTR_MEDIA_TITLE) == MOCK_TITLE_NAME
    assert mock_attrs.get(ATTR_MEDIA_CONTENT_TYPE) == MOCK_TITLE_TYPE


async def test_device_info_is_set_from_status_correctly(hass):
    """Test that device info is set correctly from status update."""
    mock_d_registry = mock_device_registry(hass)
    with patch("pyps4_2ndscreen.ps4.get_status", return_value=MOCK_STATUS_STANDBY):
        mock_entity_id = await setup_mock_component(hass)

    await hass.async_block_till_done()

    # Reformat mock status-sw_version for assertion.
    mock_version = MOCK_STATUS_STANDBY["system-version"]
    mock_version = mock_version[1:4]
    mock_version = "{}.{}".format(mock_version[0], mock_version[1:])

    mock_state = hass.states.get(mock_entity_id).state

    mock_d_entries = mock_d_registry.devices
    mock_entry = mock_d_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_HOST_ID)}, connections={()}
    )
    assert mock_state == STATE_STANDBY

    assert len(mock_d_entries) == 1
    assert mock_entry.name == MOCK_HOST_NAME
    assert mock_entry.model == MOCK_DEVICE_MODEL
    assert mock_entry.sw_version == mock_version
    assert mock_entry.identifiers == {(DOMAIN, MOCK_HOST_ID)}


async def test_device_info_is_assummed(hass):
    """Test that device info is assumed if device is unavailable."""
    # Create a device registry entry with device info.
    mock_d_registry = mock_device_registry(hass)
    mock_d_registry.async_get_or_create(
        config_entry_id=MOCK_ENTRY_ID,
        name=MOCK_HOST_NAME,
        model=MOCK_DEVICE_MODEL,
        identifiers={(DOMAIN, MOCK_HOST_ID)},
        sw_version=MOCK_HOST_VERSION,
    )
    mock_d_entries = mock_d_registry.devices
    assert len(mock_d_entries) == 1

    # Create a entity_registry entry which is using identifiers from device.
    mock_unique_id = ps4.format_unique_id(MOCK_CREDS, MOCK_HOST_ID)
    mock_e_registry = mock_registry(hass)
    mock_e_registry.async_get_or_create(
        "media_player", DOMAIN, mock_unique_id, config_entry=MOCK_CONFIG
    )
    mock_entity_id = mock_e_registry.async_get_entity_id(
        "media_player", DOMAIN, mock_unique_id
    )

    mock_entity_id = await setup_mock_component(hass)
    mock_state = hass.states.get(mock_entity_id).state

    # Ensure that state is not set.
    assert mock_state == STATE_UNKNOWN

    # Ensure that entity_id is the same as the existing.
    mock_entities = hass.states.async_entity_ids()
    assert len(mock_entities) == 1
    assert mock_entities[0] == mock_entity_id


async def test_device_info_assummed_works(hass):
    """Reverse test that device info assumption works."""
    mock_d_registry = mock_device_registry(hass)
    mock_entity_id = await setup_mock_component(hass)
    mock_state = hass.states.get(mock_entity_id).state
    mock_d_entries = mock_d_registry.devices

    # Ensure that state is not set.
    assert mock_state == STATE_UNKNOWN

    # With no state/status and no existing entries, registry should be empty.
    assert not mock_d_entries


async def test_turn_on(hass):
    """Test that turn on service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_func = "{}{}".format(
        "homeassistant.components.ps4.media_player.", "pyps4.Ps4Async.wakeup"
    )

    with patch(mock_func) as mock_call:
        await hass.services.async_call(
            "media_player", "turn_on", {ATTR_ENTITY_ID: mock_entity_id}
        )
        await hass.async_block_till_done()

    assert len(mock_call.mock_calls) == 1


async def test_turn_off(hass):
    """Test that turn off service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_func = "{}{}".format(
        "homeassistant.components.ps4.media_player.", "pyps4.Ps4Async.standby"
    )

    with patch(mock_func) as mock_call:
        await hass.services.async_call(
            "media_player", "turn_off", {ATTR_ENTITY_ID: mock_entity_id}
        )
        await hass.async_block_till_done()

    assert len(mock_call.mock_calls) == 1


async def test_toggle(hass):
    """Test that toggle service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_func = "{}{}".format(
        "homeassistant.components.ps4.media_player.", "pyps4.Ps4Async.toggle"
    )

    with patch(mock_func) as mock_call:
        await hass.services.async_call(
            "media_player", "toggle", {ATTR_ENTITY_ID: mock_entity_id}
        )
        await hass.async_block_till_done()

    assert len(mock_call.mock_calls) == 1


async def test_media_pause(hass):
    """Test that media pause service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_func = "{}{}".format(
        "homeassistant.components.ps4.media_player.", "pyps4.Ps4Async.remote_control"
    )

    with patch(mock_func) as mock_call:
        await hass.services.async_call(
            "media_player", "media_pause", {ATTR_ENTITY_ID: mock_entity_id}
        )
        await hass.async_block_till_done()

    assert len(mock_call.mock_calls) == 1


async def test_media_stop(hass):
    """Test that media stop service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_func = "{}{}".format(
        "homeassistant.components.ps4.media_player.", "pyps4.Ps4Async.remote_control"
    )

    with patch(mock_func) as mock_call:
        await hass.services.async_call(
            "media_player", "media_stop", {ATTR_ENTITY_ID: mock_entity_id}
        )
        await hass.async_block_till_done()

    assert len(mock_call.mock_calls) == 1


async def test_select_source(hass, patch_load_json):
    """Test that select source service calls function with title."""
    patch_load_json.return_value = {MOCK_TITLE_ID: MOCK_GAMES_DATA}
    with patch("pyps4_2ndscreen.ps4.get_status", return_value=MOCK_STATUS_IDLE):
        mock_entity_id = await setup_mock_component(hass)

    with patch("pyps4_2ndscreen.ps4.Ps4Async.start_title") as mock_call, patch(
        "homeassistant.components.ps4.media_player.PS4Device.async_update"
    ):
        # Test with title name.
        await hass.services.async_call(
            "media_player",
            "select_source",
            {ATTR_ENTITY_ID: mock_entity_id, ATTR_INPUT_SOURCE: MOCK_TITLE_NAME},
            blocking=True,
        )

    assert len(mock_call.mock_calls) == 1


async def test_select_source_caps(hass, patch_load_json):
    """Test that select source service calls function with upper case title."""
    patch_load_json.return_value = {MOCK_TITLE_ID: MOCK_GAMES_DATA}
    with patch("pyps4_2ndscreen.ps4.get_status", return_value=MOCK_STATUS_IDLE):
        mock_entity_id = await setup_mock_component(hass)

    with patch("pyps4_2ndscreen.ps4.Ps4Async.start_title") as mock_call, patch(
        "homeassistant.components.ps4.media_player.PS4Device.async_update"
    ):
        # Test with title name in caps.
        await hass.services.async_call(
            "media_player",
            "select_source",
            {
                ATTR_ENTITY_ID: mock_entity_id,
                ATTR_INPUT_SOURCE: MOCK_TITLE_NAME.upper(),
            },
            blocking=True,
        )

    assert len(mock_call.mock_calls) == 1


async def test_select_source_id(hass, patch_load_json):
    """Test that select source service calls function with Title ID."""
    patch_load_json.return_value = {MOCK_TITLE_ID: MOCK_GAMES_DATA}
    with patch("pyps4_2ndscreen.ps4.get_status", return_value=MOCK_STATUS_IDLE):
        mock_entity_id = await setup_mock_component(hass)

    with patch("pyps4_2ndscreen.ps4.Ps4Async.start_title") as mock_call, patch(
        "homeassistant.components.ps4.media_player.PS4Device.async_update"
    ):
        # Test with title ID.
        await hass.services.async_call(
            "media_player",
            "select_source",
            {ATTR_ENTITY_ID: mock_entity_id, ATTR_INPUT_SOURCE: MOCK_TITLE_ID},
            blocking=True,
        )

    assert len(mock_call.mock_calls) == 1


async def test_ps4_send_command(hass):
    """Test that ps4 send command service calls function."""
    mock_entity_id = await setup_mock_component(hass)

    with patch("pyps4_2ndscreen.ps4.Ps4Async.remote_control") as mock_call:
        await hass.services.async_call(
            DOMAIN,
            "send_command",
            {ATTR_ENTITY_ID: mock_entity_id, ATTR_COMMAND: "ps"},
            blocking=True,
        )

    assert len(mock_call.mock_calls) == 1


async def test_entry_is_unloaded(hass):
    """Test that entry is unloaded."""
    mock_entry = MockConfigEntry(
        domain=ps4.DOMAIN, data=MOCK_DATA, version=VERSION, entry_id=MOCK_ENTRY_ID
    )
    mock_entity_id = await setup_mock_component(hass, mock_entry)
    mock_unload = await ps4.async_unload_entry(hass, mock_entry)

    assert mock_unload is True
    assert not hass.data[PS4_DATA].devices

    # Test that callback listener for entity is removed from protocol.
    assert not hass.data[PS4_DATA].protocol.callbacks

    assert hass.states.get(mock_entity_id) is None


async def test_options_port_startup(hass):
    """Test options port used on startup."""
    mock_options = {CONF_PORT: MOCK_OPTIONS_PORT}
    mock_entry = MockConfigEntry(
        domain=ps4.DOMAIN,
        data=MOCK_DATA,
        version=VERSION,
        entry_id=MOCK_ENTRY_ID,
        options=mock_options,
    )

    with patch(
        "pyps4_2ndscreen.ps4.async_create_ddp_endpoint",
        return_value=(MagicMock(), MagicMock()),
    ):
        await setup_mock_component(hass, mock_entry)

    # Test that entity does not subscribe to default protocol
    assert not hass.data[PS4_DATA].protocol.callbacks


async def test_options_port_startup_fail(hass):
    """Test options port fails on startup."""
    mock_options = {CONF_PORT: MOCK_OPTIONS_PORT}
    mock_entry = MockConfigEntry(
        domain=ps4.DOMAIN,
        data=MOCK_DATA,
        version=VERSION,
        entry_id=MOCK_ENTRY_ID,
        options=mock_options,
    )

    with patch(
        "pyps4_2ndscreen.ps4.async_create_ddp_endpoint", return_value=(None, None)
    ):
        await setup_mock_component(hass, mock_entry)

    # Test that entity subscribes to default protocol
    assert len(hass.data[PS4_DATA].protocol.callbacks) == 1


async def test_options_port_fail(hass):
    """Test port options fail."""
    mock_options_default = {CONF_PORT: DEFAULT_PORT}
    mock_options_1 = {CONF_PORT: MOCK_OPTIONS_PORT}
    mock_entry = MockConfigEntry(
        domain=ps4.DOMAIN,
        data=MOCK_DATA,
        version=VERSION,
        entry_id=MOCK_ENTRY_ID,
        options=mock_options_default,
    )
    await setup_mock_component(hass, mock_entry)
    hass.data[PS4_DATA].protocol.close = MagicMock()
    mock_entry.options = mock_options_1
    with patch(
        "pyps4_2ndscreen.ps4.Ps4Async.change_ddp_endpoint", return_value=False
    ) as mock_call, patch(
        "homeassistant.components.ps4.media_player.PS4Device.subscribe_to_protocol"
    ) as mock_subscribe:
        await ps4.media_player.update_listener(hass, mock_entry)
    mock_call.assert_awaited_once_with(MOCK_OPTIONS_PORT, False)
    mock_subscribe.assert_not_called()

    # Test No-OP if options port is same as current port.
    mock_entry.options = mock_options_default
    with patch("pyps4_2ndscreen.ps4.Ps4Async.change_ddp_endpoint") as mock_call, patch(
        "homeassistant.components.ps4.media_player.PS4Device.subscribe_to_protocol"
    ) as mock_subscribe:
        await ps4.media_player.update_listener(hass, mock_entry)
    mock_call.assert_not_awaited()
    mock_subscribe.assert_not_called()
    hass.data[PS4_DATA].protocol.close.assert_not_called()


async def test_options_port_updated(hass):
    """Test port options updated. 3 cases.

    Case 1: Default port -> Options port
    Case 2: Options port -> Default port
    Case 3: Options port -> Options port
    """
    mock_options_default = {CONF_PORT: DEFAULT_PORT}
    mock_options_1 = {CONF_PORT: MOCK_OPTIONS_PORT}
    mock_options_2 = {CONF_PORT: MOCK_OPTIONS_PORT_2}
    mock_entry_default = MockConfigEntry(
        domain=ps4.DOMAIN,
        data=MOCK_DATA,
        version=VERSION,
        entry_id=MOCK_ENTRY_ID,
        options=mock_options_default,
    )
    mock_entry_1 = MockConfigEntry(
        domain=ps4.DOMAIN,
        data=MOCK_DATA,
        version=VERSION,
        entry_id=f"{MOCK_ENTRY_ID}1",
        options=mock_options_1,
    )
    mock_entry_2 = MockConfigEntry(
        domain=ps4.DOMAIN,
        data=MOCK_DATA,
        version=VERSION,
        entry_id=f"{MOCK_ENTRY_ID}2",
        options=mock_options_2,
    )
    mock_entry_1.add_to_hass(hass)
    mock_entry_2.add_to_hass(hass)

    await setup_mock_component(hass, mock_entry_default)
    hass.data[PS4_DATA].protocol.close = MagicMock()
    assert len(hass.states.async_entity_ids()) == 3

    # Test Default port to Options port
    mock_entry_default.options = mock_options_1
    with patch(
        "pyps4_2ndscreen.ps4.Ps4Async.change_ddp_endpoint", return_value=True
    ) as mock_call, patch(
        "homeassistant.components.ps4.media_player.PS4Device.subscribe_to_protocol"
    ) as mock_subscribe:
        await ps4.media_player.update_listener(hass, mock_entry_default)
    # Default protocol should not close with arg[1] as False
    mock_call.assert_awaited_once_with(MOCK_OPTIONS_PORT, False)
    mock_subscribe.assert_called_once()

    # Test Options port to Default port
    mock_entry_1.options = mock_options_default
    with patch(
        "pyps4_2ndscreen.ps4.Ps4Async.change_ddp_endpoint", return_value=True
    ) as mock_call, patch(
        "homeassistant.components.ps4.media_player.PS4Device.subscribe_to_protocol"
    ) as mock_subscribe:
        await ps4.media_player.update_listener(hass, mock_entry_1)
    # Endpoint is manually set to default endpoint/protocol
    mock_call.assert_not_awaited()
    mock_subscribe.assert_called_once()

    # Test Options port to Options port
    mock_entry_2.options = mock_options_1
    with patch(
        "pyps4_2ndscreen.ps4.Ps4Async.change_ddp_endpoint", return_value=True
    ) as mock_call, patch(
        "homeassistant.components.ps4.media_player.PS4Device.subscribe_to_protocol"
    ) as mock_subscribe:
        await ps4.media_player.update_listener(hass, mock_entry_2)
    # Non-default protocol should close with arg[1] as True
    mock_call.assert_awaited_once_with(MOCK_OPTIONS_PORT, True)
    mock_subscribe.assert_called_once()

    # Assert default protocol is never closed
    hass.data[PS4_DATA].protocol.close.assert_not_called()
