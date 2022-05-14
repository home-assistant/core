"""Test the Scrape config flow."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.scrape.const import CONF_INDEX, CONF_SELECT, DOMAIN
from homeassistant.const import (
    CONF_NAME,
    CONF_RESOURCE,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import MockRestData

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=MockRestData("test_scrape_sensor"),
    ), patch(
        "homeassistant.components.scrape.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_NAME: "Release",
                CONF_SELECT: ".current-version h1",
                CONF_VALUE_TEMPLATE: "{{ value.split(':')[1] }}",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Release"
    assert result2["options"] == {
        "resource": "https://www.home-assistant.io",
        "name": "Release",
        "select": ".current-version h1",
        "value_template": "{{ value.split(':')[1] }}",
        "index": 0.0,
        "verify_ssl": True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=MockRestData("test_scrape_sensor"),
    ), patch(
        "homeassistant.components.scrape.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_NAME: "Release",
                CONF_SELECT: ".current-version h1",
                CONF_VALUE_TEMPLATE: "{{ value.split(':')[1] }}",
                CONF_INDEX: 0,
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Release"
    assert result2["options"] == {
        "resource": "https://www.home-assistant.io",
        "name": "Release",
        "select": ".current-version h1",
        "value_template": "{{ value.split(':')[1] }}",
        "index": 0,
        "verify_ssl": True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
    """Test import of yaml already exist."""

    MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "resource": "https://www.home-assistant.io",
            "name": "Release",
            "select": ".current-version h1",
            "value_template": "{{ value.split(':')[1] }}",
            "index": 0,
            "verify_ssl": True,
        },
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=MockRestData("test_scrape_sensor"),
    ), patch(
        "homeassistant.components.scrape.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_NAME: "Release",
                CONF_SELECT: ".current-version h1",
                CONF_VALUE_TEMPLATE: "{{ value.split(':')[1] }}",
                CONF_INDEX: 0,
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "already_configured"


async def test_options_form(hass: HomeAssistant) -> None:
    """Test we get the form in options."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "resource": "https://www.home-assistant.io",
            "name": "Release",
            "select": ".current-version h1",
            "value_template": "{{ value.split(':')[1] }}",
            "index": 0,
            "verify_ssl": True,
        },
        entry_id="1",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=MockRestData("test_scrape_sensor"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=MockRestData("test_scrape_sensor"),
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "value_template": "{{ value.split(':')[1] }}",
                "index": 1.0,
                "verify_ssl": True,
            },
        )

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        "resource": "https://www.home-assistant.io",
        "name": "Release",
        "select": ".current-version h1",
        "value_template": "{{ value.split(':')[1] }}",
        "index": 1.0,
        "verify_ssl": True,
    }
    entry_check = hass.config_entries.async_get_entry("1")
    assert entry_check.state == config_entries.ConfigEntryState.LOADED
    assert entry_check.update_listeners is not None
