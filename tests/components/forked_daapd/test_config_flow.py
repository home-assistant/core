"""The config flow tests for the forked_daapd media player platform."""
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.forked_daapd.const import (
    CONF_LIBRESPOT_JAVA_PORT,
    CONF_MAX_PLAYLISTS,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    DOMAIN,
)
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_PUSH,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

from tests.async_mock import patch
from tests.common import MockConfigEntry

SAMPLE_CONFIG = {
    "websocket_port": 3688,
    "version": "25.0",
    "buildoptions": [
        "ffmpeg",
        "iTunes XML",
        "Spotify",
        "LastFM",
        "MPD",
        "Device verification",
        "Websockets",
        "ALSA",
    ],
}


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create hass config_entry fixture."""
    data = {
        CONF_HOST: "192.168.1.1",
        CONF_PORT: "2345",
        CONF_PASSWORD: "",
    }
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="",
        data=data,
        options={},
        system_options={},
        source=SOURCE_USER,
        connection_class=CONN_CLASS_LOCAL_PUSH,
        entry_id=1,
    )


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_config_flow(hass, config_entry):
    """Test that the user step works."""
    with patch(
        "homeassistant.components.forked_daapd.config_flow.ForkedDaapdAPI.test_connection"
    ) as mock_test_connection, patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI.get_request",
        autospec=True,
    ) as mock_get_request:
        mock_get_request.return_value = SAMPLE_CONFIG
        mock_test_connection.return_value = ["ok", "My Music on myhost"]
        config_data = config_entry.data
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config_data
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "My Music on myhost"
        assert result["data"][CONF_HOST] == config_data[CONF_HOST]
        assert result["data"][CONF_PORT] == config_data[CONF_PORT]
        assert result["data"][CONF_PASSWORD] == config_data[CONF_PASSWORD]

        # Also test that creating a new entry with the same host aborts
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config_entry.data,
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_updates_title(hass, config_entry):
    """Test that zeroconf updates title and aborts with same host."""
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "different host"}).add_to_hass(hass)
    config_entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    discovery_info = {
        "host": "192.168.1.1",
        "port": 23,
        "properties": {"mtd-version": "27.0", "Machine Name": "zeroconf_test"},
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )
    await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert config_entry.title == "zeroconf_test"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_config_flow_no_websocket(hass, config_entry):
    """Test config flow setup without websocket enabled on server."""
    with patch(
        "homeassistant.components.forked_daapd.config_flow.ForkedDaapdAPI.test_connection"
    ) as mock_test_connection:
        # test invalid config data
        mock_test_connection.return_value = ["websocket_not_enabled"]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config_entry.data
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_config_flow_zeroconf_invalid(hass):
    """Test that an invalid zeroconf entry doesn't work."""
    # test with no discovery properties
    discovery_info = {"host": "127.0.0.1", "port": 23}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )  # doesn't create the entry, tries to show form but gets abort
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "not_forked_daapd"
    # test with forked-daapd version < 27
    discovery_info = {
        "host": "127.0.0.1",
        "port": 23,
        "properties": {"mtd-version": "26.3", "Machine Name": "forked-daapd"},
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )  # doesn't create the entry, tries to show form but gets abort
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "not_forked_daapd"
    # test with verbose mtd-version from Firefly
    discovery_info = {
        "host": "127.0.0.1",
        "port": 23,
        "properties": {"mtd-version": "0.2.4.1", "Machine Name": "firefly"},
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )  # doesn't create the entry, tries to show form but gets abort
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "not_forked_daapd"


async def test_config_flow_zeroconf_valid(hass):
    """Test that a valid zeroconf entry works."""
    discovery_info = {
        "host": "192.168.1.1",
        "port": 23,
        "properties": {
            "mtd-version": "27.0",
            "Machine Name": "zeroconf_test",
            "Machine ID": "5E55EEFF",
        },
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_options_flow(hass, config_entry):
    """Test config flow options."""

    with patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI.get_request",
        autospec=True,
    ) as mock_get_request:
        mock_get_request.return_value = SAMPLE_CONFIG
        config_entry.add_to_hass(hass)
        await config_entry.async_setup(hass)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TTS_PAUSE_TIME: 0.05,
                CONF_TTS_VOLUME: 0.8,
                CONF_LIBRESPOT_JAVA_PORT: 0,
                CONF_MAX_PLAYLISTS: 8,
            },
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
