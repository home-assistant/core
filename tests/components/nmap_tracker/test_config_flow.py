"""Test the Nmap Tracker config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.components.nmap_tracker.const import (
    CONF_HOME_INTERVAL,
    CONF_OPTIONS,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS
from homeassistant.core import CoreState, HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "hosts", ["1.1.1.1", "192.168.1.0/24", "192.168.1.0/24,192.168.2.0/24"]
)
async def test_form(hass: HomeAssistant, hosts: str, mock_get_source_ip) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    schema_defaults = result["data_schema"]({})
    assert CONF_SCAN_INTERVAL not in schema_defaults

    with patch(
        "homeassistant.components.nmap_tracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOSTS: hosts,
                CONF_HOME_INTERVAL: 3,
                CONF_OPTIONS: DEFAULT_OPTIONS,
                CONF_EXCLUDE: "4.4.4.4",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == f"Nmap Tracker {hosts}"
    assert result2["data"] == {}
    assert result2["options"] == {
        CONF_HOSTS: hosts,
        CONF_HOME_INTERVAL: 3,
        CONF_OPTIONS: DEFAULT_OPTIONS,
        CONF_EXCLUDE: "4.4.4.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_range(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test we get the form and can take an ip range."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nmap_tracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOSTS: "192.168.0.5-12",
                CONF_HOME_INTERVAL: 3,
                CONF_OPTIONS: DEFAULT_OPTIONS,
                CONF_EXCLUDE: "4.4.4.4",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Nmap Tracker 192.168.0.5-12"
    assert result2["data"] == {}
    assert result2["options"] == {
        CONF_HOSTS: "192.168.0.5-12",
        CONF_HOME_INTERVAL: 3,
        CONF_OPTIONS: DEFAULT_OPTIONS,
        CONF_EXCLUDE: "4.4.4.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_hosts(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test invalid hosts passed in."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOSTS: "not an ip block",
            CONF_HOME_INTERVAL: 3,
            CONF_OPTIONS: DEFAULT_OPTIONS,
            CONF_EXCLUDE: "",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_HOSTS: "invalid_hosts"}


async def test_form_already_configured(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test duplicate host list."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_HOSTS: "192.168.0.0/20",
            CONF_HOME_INTERVAL: 3,
            CONF_OPTIONS: DEFAULT_OPTIONS,
            CONF_EXCLUDE: "4.4.4.4",
        },
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOSTS: "192.168.0.0/20",
            CONF_HOME_INTERVAL: 3,
            CONF_OPTIONS: DEFAULT_OPTIONS,
            CONF_EXCLUDE: "",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_form_invalid_excludes(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test invalid excludes passed in."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOSTS: "3.3.3.3",
            CONF_HOME_INTERVAL: 3,
            CONF_OPTIONS: DEFAULT_OPTIONS,
            CONF_EXCLUDE: "not an exclude",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_EXCLUDE: "invalid_hosts"}


async def test_options_flow(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test we can edit options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_HOSTS: "192.168.1.0/24",
            CONF_HOME_INTERVAL: 3,
            CONF_OPTIONS: DEFAULT_OPTIONS,
            CONF_EXCLUDE: "4.4.4.4",
        },
    )
    config_entry.add_to_hass(hass)
    hass.state = CoreState.stopped

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    assert result["data_schema"]({}) == {
        CONF_EXCLUDE: "4.4.4.4",
        CONF_HOME_INTERVAL: 3,
        CONF_HOSTS: "192.168.1.0/24",
        CONF_CONSIDER_HOME: 180,
        CONF_SCAN_INTERVAL: 120,
        CONF_OPTIONS: "-F -T4 --min-rate 10 --host-timeout 5s",
    }

    with patch(
        "homeassistant.components.nmap_tracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOSTS: "192.168.1.0/24, 192.168.2.0/24",
                CONF_HOME_INTERVAL: 5,
                CONF_CONSIDER_HOME: 500,
                CONF_OPTIONS: "-sn",
                CONF_EXCLUDE: "4.4.4.4, 5.5.5.5",
                CONF_SCAN_INTERVAL: 10,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_HOSTS: "192.168.1.0/24,192.168.2.0/24",
        CONF_HOME_INTERVAL: 5,
        CONF_CONSIDER_HOME: 500,
        CONF_OPTIONS: "-sn",
        CONF_EXCLUDE: "4.4.4.4,5.5.5.5",
        CONF_SCAN_INTERVAL: 10,
    }
    assert len(mock_setup_entry.mock_calls) == 1
