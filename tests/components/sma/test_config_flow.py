"""Test the sma config flow."""
from unittest.mock import patch

import aiohttp

from homeassistant import setup
from homeassistant.components.sma.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers import entity_registry as er

from . import (
    MOCK_DEVICE,
    MOCK_IMPORT,
    MOCK_LEGACY_ENTRY,
    MOCK_SETUP_DATA,
    MOCK_USER_INPUT,
    _patch_async_setup_entry,
    _patch_validate_input,
)


async def test_form(hass, aioclient_mock):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch("pysma.SMA.new_session", return_value=True), patch(
        "pysma.SMA.device_info", return_value=MOCK_DEVICE
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT["host"]
    assert result["data"] == MOCK_SETUP_DATA

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass, aioclient_mock):
    """Test we handle cannot connect error."""
    aioclient_mock.get("https://1.1.1.1/data/l10n/en-US.json", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass, aioclient_mock):
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysma.SMA.new_session", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_retrieve_device_info(hass, aioclient_mock):
    """Test we handle cannot retrieve device info error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysma.SMA.new_session", return_value=True), patch(
        "pysma.SMA.read", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_retrieve_device_info"}


async def test_form_unexpected_exception(hass):
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with _patch_validate_input(side_effect=Exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass):
    """Test starting a flow by user when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with _patch_validate_input():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == MOCK_DEVICE["serial"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with _patch_validate_input():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_import(hass):
    """Test we can import."""
    entity_registry = er.async_get(hass)
    entity_registry._register_entry(MOCK_LEGACY_ENTRY)

    await setup.async_setup_component(hass, "persistent_notification", {})

    with _patch_validate_input():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_IMPORT,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT["host"]
    assert result["data"] == MOCK_IMPORT

    assert MOCK_LEGACY_ENTRY.original_name not in result["data"]["sensors"]
    assert "pv_power_a" in result["data"]["sensors"]

    entity = entity_registry.async_get(MOCK_LEGACY_ENTRY.entity_id)
    assert entity.unique_id == f"{MOCK_DEVICE['serial']}-6380_40251E00_0"
