"""Test the Scrape config flow."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.rest.data import DEFAULT_TIMEOUT
from homeassistant.components.rest.schema import DEFAULT_METHOD, DEFAULT_VERIFY_SSL
from homeassistant.components.scrape import DOMAIN
from homeassistant.components.scrape.const import (
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_SCAN_INTERVAL,
)
from homeassistant.const import (
    CONF_METHOD,
    CONF_NAME,
    CONF_RESOURCE,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import MockRestData

from tests.common import MockConfigEntry

RESOURCE_CONFIG = {
    CONF_RESOURCE: "https://www.home-assistant.io",
    CONF_METHOD: DEFAULT_METHOD,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}
SENSOR_CONFIG = {
    CONF_NAME: "Current version",
    CONF_SELECT: ".current-version h1",
    CONF_INDEX: 0,
}


async def test_form(hass: HomeAssistant, get_data: MockRestData) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.rest.RestData",
        return_value=get_data,
    ) as mock_data, patch(
        "homeassistant.components.scrape.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
                CONF_SCAN_INTERVAL: 600.0,
            },
        )
        await hass.async_block_till_done()
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["version"] == 1
    assert result3["options"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10.0,
        CONF_SCAN_INTERVAL: 600.0,
        CONF_NAME: "Current version",
        CONF_SELECT: ".current-version h1",
        CONF_INDEX: 0.0,
    }

    assert len(mock_data.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_fails(hass: HomeAssistant, get_data: MockRestData) -> None:
    """Test config flow error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.rest.RestData",
        side_effect=HomeAssistantError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
                CONF_SCAN_INTERVAL: 600.0,
            },
        )

    assert result2["errors"] == {"base": "resource_error"}

    with patch("homeassistant.components.rest.RestData", return_value=get_data,), patch(
        "homeassistant.components.scrape.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
                CONF_SCAN_INTERVAL: 600.0,
            },
        )
        await hass.async_block_till_done()
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Current version"
    assert result4["options"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10.0,
        CONF_SCAN_INTERVAL: 600.0,
        CONF_NAME: "Current version",
        CONF_SELECT: ".current-version h1",
        CONF_INDEX: 0.0,
    }


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={**RESOURCE_CONFIG, **SENSOR_CONFIG}
    )
    entry.add_to_hass(hass)

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.current_version")
    assert state.state == "Current Version: 2021.12.10"

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    mocker2 = MockRestData("test_scrape_sensor_authentication")
    with patch("homeassistant.components.rest.RestData", return_value=mocker2):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_SELECT: ".return",
                CONF_INDEX: 0,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10.0,
        CONF_SCAN_INTERVAL: 600.0,
        CONF_NAME: "Current version",
        CONF_SELECT: ".return",
        CONF_INDEX: 0.0,
    }

    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    # Check the state of the entity has changed as expected
    state = hass.states.get("sensor.current_version")
    assert state.state == "secret text"
