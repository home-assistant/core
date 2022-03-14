"""Tests for Wemo config flow."""

from datetime import datetime
from socket import timeout

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.maxcube import (
    DOMAIN,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, patch


class MaxCubeMocked:
    """Mock class for maxcube-api library."""

    devices = []

    def __init__(self, host: str, port: int = 123, now=datetime.now):
        """Init. Fail with wrong host."""
        if host == "wrong":
            raise Exception("Some connect error")
        if host == "timeouthost":
            raise timeout()

    def disconnect(self):
        """Disconnect."""


@patch("maxcube.cube.MaxCube", new=MaxCubeMocked)
async def test_wrong_host(hass: HomeAssistant) -> None:
    """Test wrong host that can't connect."""

    result = await hass.config_entries.flow.async_init(
        "maxcube",
        context={"source": SOURCE_USER},
    )

    config = {"host": "wrong"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], config)

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "connection_error"


@patch("maxcube.cube.MaxCube", new=MaxCubeMocked)
async def test_mandatory_params_only(hass: HomeAssistant) -> None:
    """Test minimum config params."""

    result = await hass.config_entries.flow.async_init(
        "maxcube",
        context={"source": SOURCE_USER},
    )

    config = {"host": "123.123.123.123"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], config)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Cube@123.123.123.123:62910"
    assert result["data"]["host"] == "123.123.123.123"
    # default values
    assert result["data"]["port"] == 62910
    assert result["data"]["scan_interval"] == 300


@patch("maxcube.cube.MaxCube", new=MaxCubeMocked)
async def test_all_params(hass: HomeAssistant) -> None:
    """Test with all config params."""

    result = await hass.config_entries.flow.async_init(
        "maxcube",
        context={"source": SOURCE_USER},
    )

    config = {"host": "123.123.123.123", "port": 12345, "scan_interval": 11}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], config)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Cube@123.123.123.123:12345"
    assert result["data"]["host"] == "123.123.123.123"
    assert result["data"]["port"] == 12345
    assert result["data"]["scan_interval"] == 11


@patch("maxcube.cube.MaxCube", new=MaxCubeMocked)
async def test_step_import_mandatory_params(hass):
    """Test for import step."""

    data = {
        "host": "11.22.33.44",
    }
    result = await hass.config_entries.flow.async_init(
        "maxcube", context={"source": config_entries.SOURCE_IMPORT}, data=data
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Cube@11.22.33.44:62910"
    assert result["data"]["host"] == "11.22.33.44"
    assert result["data"].get("port") is None
    assert result["data"].get("scan_interval") is None


@patch("maxcube.cube.MaxCube", new=MaxCubeMocked)
async def test_step_import_all_params(hass):
    """Test for import step."""

    data = {"host": "11.22.33.44", "port": 9988, "scan_interval": 77}
    result = await hass.config_entries.flow.async_init(
        "maxcube", context={"source": config_entries.SOURCE_IMPORT}, data=data
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Cube@11.22.33.44:9988"
    assert result["data"]["host"] == "11.22.33.44"
    assert result["data"].get("port") == 9988
    assert result["data"].get("scan_interval") == 77


@patch("maxcube.cube.MaxCube", new=MaxCubeMocked)
async def test_step_import_wrong_host(hass):
    """Test for import step."""

    data = {
        "host": "wrong",
    }
    result = await hass.config_entries.flow.async_init(
        "maxcube", context={"source": config_entries.SOURCE_IMPORT}, data=data
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


@patch("homeassistant.components.maxcube.MaxCube", new=MaxCubeMocked)
async def test_setup_entry(hass: HomeAssistant, hass_config) -> None:
    """Test setup."""

    gateway = {"host": "timeouthost"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="112233",
        data={**gateway, **hass_config},
        options={},
        version=1,
    )
    entry.add_to_hass(hass)

    assert not await async_setup_entry(hass, entry)


@patch("homeassistant.components.maxcube.MaxCube", new=MaxCubeMocked)
async def test_unload_entry(hass, hass_config):
    """Test unload."""

    gateway = {"host": "something"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="112233",
        data={**gateway, **hass_config},
        options={},
        version=1,
    )
    entry.add_to_hass(hass)

    assert await async_setup_entry(hass, entry)
    assert await async_unload_entry(hass, entry)
    # unload second time
    assert await async_unload_entry(hass, entry)
