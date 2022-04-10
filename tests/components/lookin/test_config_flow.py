"""Define tests for the lookin config flow."""
from __future__ import annotations

import dataclasses
from unittest.mock import patch

from aiolookin import NoUsableService

from homeassistant import config_entries
from homeassistant.components.lookin.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    DEFAULT_ENTRY_TITLE,
    DEVICE_ID,
    IP_ADDRESS,
    MODULE,
    ZEROCONF_DATA,
    _patch_get_info,
)

from tests.common import MockConfigEntry


async def test_manual_setup(hass: HomeAssistant):
    """Test manually setting up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_get_info(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["title"] == DEFAULT_ENTRY_TITLE
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_setup_already_exists(hass: HomeAssistant):
    """Test manually setting up and the device already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=DEVICE_ID
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_get_info():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_manual_setup_device_offline(hass: HomeAssistant):
    """Test manually setting up, device offline."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_get_info(exception=NoUsableService):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {CONF_HOST: "cannot_connect"}


async def test_manual_setup_unknown_exception(hass: HomeAssistant):
    """Test manually setting up, unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_get_info(exception=Exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


async def test_discovered_zeroconf(hass):
    """Test we can setup when discovered from zeroconf."""

    with _patch_get_info():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_get_info(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {CONF_HOST: IP_ADDRESS}
    assert result2["title"] == DEFAULT_ENTRY_TITLE
    assert mock_async_setup_entry.called

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    zc_data_new_ip = dataclasses.replace(ZEROCONF_DATA)
    zc_data_new_ip.host = "127.0.0.2"

    with _patch_get_info(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zc_data_new_ip,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "127.0.0.2"


async def test_discovered_zeroconf_cannot_connect(hass):
    """Test we abort if we cannot connect when discovered from zeroconf."""

    with _patch_get_info(exception=NoUsableService):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


async def test_discovered_zeroconf_unknown_exception(hass):
    """Test we abort if we get an unknown exception when discovered from zeroconf."""

    with _patch_get_info(exception=Exception):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"
