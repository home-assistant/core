"""Test the PulseAudio config flow."""
from unittest.mock import PropertyMock, patch

from pulsectl import PulseError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.pulseaudio.const import (
    CONF_MEDIAPLAYER_SINKS,
    CONF_MEDIAPLAYER_SOURCES,
    CONF_SERVER,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_SERVER = "localhost"
TEST_UNIQUE_ID = f"{DOMAIN}-{TEST_SERVER}"


@pytest.fixture(name="pulseaudio_connect", autouse=True)
def pulseaudio_connect_fixture():
    """Mock PulseAudio connection."""

    class PulseItemMock:
        def __init__(self, name: str):
            self.name = name

    with patch("pulsectl.Pulse.__init__", return_value=None), patch(
        "pulsectl.Pulse.sink_list",
        return_value=[PulseItemMock("sink1"), PulseItemMock("sink2")],
    ), patch(
        "pulsectl.Pulse.source_list",
        return_value=[PulseItemMock("source1"), PulseItemMock("source2")],
    ), patch(
        "pulsectl.Pulse.module_list",
        return_value=[],
    ), patch(
        "pulsectl.Pulse.connected",
        new_callable=PropertyMock,
        create=True,
        return_value=True,
    ):
        yield


async def test_config_flow_connect_success(hass: HomeAssistant):
    """Unsuccessful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SERVER: "localhost"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "localhost"
    assert result["data"] == {
        CONF_SERVER: "localhost",
    }

    await hass.config_entries.async_unload(result["result"].entry_id)


async def test_config_flow_cannot_connect(hass: HomeAssistant):
    """Unsuccessful flow manually initialized by the user."""
    with patch(
        "pulsectl.Pulse.connected",
        new_callable=PropertyMock,
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERVER: "localhost"},
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_already_configured(hass: HomeAssistant):
    """Test already configured config flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={
            CONF_SERVER: TEST_SERVER,
            CONF_MEDIAPLAYER_SINKS: [],
            CONF_MEDIAPLAYER_SOURCES: [],
        },
        title=TEST_SERVER,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SERVER: "localhost"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_config_flow_options(hass: HomeAssistant):
    """Test options config flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={
            CONF_SERVER: TEST_SERVER,
            CONF_MEDIAPLAYER_SINKS: [],
            CONF_MEDIAPLAYER_SOURCES: [],
        },
        title=TEST_SERVER,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MEDIAPLAYER_SINKS: ["sink1"],
            CONF_MEDIAPLAYER_SOURCES: ["source2"],
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        CONF_MEDIAPLAYER_SINKS: ["sink1"],
        CONF_MEDIAPLAYER_SOURCES: ["source2"],
    }
    assert await config_entry.async_unload(hass)


async def test_config_flow_options_connect_error(hass: HomeAssistant):
    """Test options config flow with PulseError."""

    with patch("pulsectl.Pulse.__init__", side_effect=PulseError()):

        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=TEST_UNIQUE_ID,
            data={
                CONF_SERVER: TEST_SERVER,
                CONF_MEDIAPLAYER_SINKS: [],
                CONF_MEDIAPLAYER_SOURCES: [],
            },
            title=TEST_SERVER,
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["errors"] == {"base": "cannot_connect"}

        assert await config_entry.async_unload(hass)


async def test_config_flow_options_error(hass: HomeAssistant):
    """Test options config flow with Exception."""

    with patch("pulsectl.Pulse.__init__", side_effect=IndexError()):

        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=TEST_UNIQUE_ID,
            data={
                CONF_SERVER: TEST_SERVER,
                CONF_MEDIAPLAYER_SINKS: [],
                CONF_MEDIAPLAYER_SOURCES: [],
            },
            title=TEST_SERVER,
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["errors"] == {"base": "unknown"}

        assert await config_entry.async_unload(hass)
