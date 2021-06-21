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

from . import (
    MOCK_DEVICE,
    MOCK_IMPORT,
    MOCK_IMPORT_DICT,
    MOCK_SETUP_DATA,
    MOCK_USER_INPUT,
    _patch_async_setup_entry,
)


async def test_form(hass):
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


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "pysma.SMA.new_session", side_effect=aiohttp.ClientError
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "pysma.SMA.new_session", return_value=False
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_cannot_retrieve_device_info(hass):
    """Test we handle cannot retrieve device info error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysma.SMA.new_session", return_value=True), patch(
        "pysma.SMA.read", return_value=False
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_retrieve_device_info"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_unexpected_exception(hass):
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "pysma.SMA.new_session", side_effect=Exception
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_already_configured(hass, mock_config_entry):
    """Test starting a flow by user when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysma.SMA.new_session", return_value=True), patch(
        "pysma.SMA.device_info", return_value=MOCK_DEVICE
    ), patch(
        "pysma.SMA.close_session", return_value=True
    ), _patch_async_setup_entry() as mock_setup_entry:

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_import(hass):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("pysma.SMA.new_session", return_value=True), patch(
        "pysma.SMA.device_info", return_value=MOCK_DEVICE
    ), patch(
        "pysma.SMA.close_session", return_value=True
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_IMPORT,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT["host"]
    assert result["data"] == MOCK_IMPORT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_sensor_dict(hass):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("pysma.SMA.new_session", return_value=True), patch(
        "pysma.SMA.device_info", return_value=MOCK_DEVICE
    ), patch(
        "pysma.SMA.close_session", return_value=True
    ), _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_IMPORT_DICT,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT["host"]
    assert result["data"] == MOCK_IMPORT_DICT
    assert len(mock_setup_entry.mock_calls) == 1
