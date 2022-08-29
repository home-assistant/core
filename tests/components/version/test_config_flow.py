"""Test the Version config flow."""
from unittest.mock import patch

from pyhaversion.consts import HaVersionChannel, HaVersionSource

from homeassistant import config_entries
from homeassistant.components.version.const import (
    CONF_BETA,
    CONF_BOARD,
    CONF_CHANNEL,
    CONF_IMAGE,
    CONF_VERSION_SOURCE,
    DEFAULT_CONFIGURATION,
    DOMAIN,
    UPDATE_COORDINATOR_UPDATE_INTERVAL,
    VERSION_SOURCE_DOCKER_HUB,
    VERSION_SOURCE_PYPI,
    VERSION_SOURCE_VERSIONS,
)
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt

from .common import MOCK_VERSION, MOCK_VERSION_DATA, setup_version_integration

from tests.common import async_fire_time_changed


async def test_reload_config_entry(hass: HomeAssistant):
    """Test reloading the config entry."""
    config_entry = await setup_version_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED

    with patch(
        "pyhaversion.HaVersion.get_version",
        return_value=(MOCK_VERSION, MOCK_VERSION_DATA),
    ):
        assert await hass.config_entries.async_reload(config_entry.entry_id)
        async_fire_time_changed(hass, dt.utcnow() + UPDATE_COORDINATOR_UPDATE_INTERVAL)
        await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert entry.state == config_entries.ConfigEntryState.LOADED


async def test_basic_form(hass: HomeAssistant) -> None:
    """Test that we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": False},
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.version.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_VERSION_SOURCE: VERSION_SOURCE_DOCKER_HUB},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == VERSION_SOURCE_DOCKER_HUB
    assert result2["data"] == {
        **DEFAULT_CONFIGURATION,
        CONF_SOURCE: HaVersionSource.CONTAINER,
        CONF_VERSION_SOURCE: VERSION_SOURCE_DOCKER_HUB,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_advanced_form_pypi(hass: HomeAssistant) -> None:
    """Show advanced form when pypi is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_VERSION_SOURCE: VERSION_SOURCE_PYPI},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "version_source"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "version_source"

    with patch(
        "homeassistant.components.version.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_BETA: True}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == VERSION_SOURCE_PYPI
    assert result["data"] == {
        **DEFAULT_CONFIGURATION,
        CONF_BETA: True,
        CONF_SOURCE: HaVersionSource.PYPI,
        CONF_VERSION_SOURCE: VERSION_SOURCE_PYPI,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_advanced_form_container(hass: HomeAssistant) -> None:
    """Show advanced form when container source is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_VERSION_SOURCE: VERSION_SOURCE_DOCKER_HUB},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "version_source"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "version_source"

    with patch(
        "homeassistant.components.version.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IMAGE: "odroid-n2-homeassistant"}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == VERSION_SOURCE_DOCKER_HUB
    assert result["data"] == {
        **DEFAULT_CONFIGURATION,
        CONF_IMAGE: "odroid-n2-homeassistant",
        CONF_SOURCE: HaVersionSource.CONTAINER,
        CONF_VERSION_SOURCE: VERSION_SOURCE_DOCKER_HUB,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_advanced_form_supervisor(hass: HomeAssistant) -> None:
    """Show advanced form when docker source is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_VERSION_SOURCE: VERSION_SOURCE_VERSIONS},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "version_source"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "version_source"

    with patch(
        "homeassistant.components.version.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CHANNEL: "Dev", CONF_IMAGE: "odroid-n2", CONF_BOARD: "ODROID N2"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{VERSION_SOURCE_VERSIONS} Dev"
    assert result["data"] == {
        **DEFAULT_CONFIGURATION,
        CONF_IMAGE: "odroid-n2",
        CONF_BOARD: "ODROID N2",
        CONF_CHANNEL: HaVersionChannel.DEV,
        CONF_SOURCE: HaVersionSource.SUPERVISOR,
        CONF_VERSION_SOURCE: VERSION_SOURCE_VERSIONS,
    }
    assert len(mock_setup_entry.mock_calls) == 1
