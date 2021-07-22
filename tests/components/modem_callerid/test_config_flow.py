"""Test Modem Caller ID config flow."""
from unittest.mock import AsyncMock, patch

import phone_modem

from homeassistant.components.modem_callerid.const import (
    DEFAULT_DEVICE,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_DEVICE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import CONF_DATA, IMPORT_DATA, _patch_config_flow_modem

from tests.common import MockConfigEntry


def _patch_setup():
    return patch(
        "homeassistant.components.modem_callerid.async_setup_entry",
        return_value=True,
    )


async def test_flow_user(hass):
    """Test user initialized flow with duplicate device."""
    mocked_modem = AsyncMock()
    with _patch_config_flow_modem(mocked_modem), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["data"] == CONF_DATA

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: DEFAULT_DEVICE},
    )

    entry.add_to_hass(hass)

    service_info = {"device": DEFAULT_DEVICE}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_error(hass):
    """Test user initialized flow with unreachable device."""
    with _patch_config_flow_modem(AsyncMock()) as modemmock:
        modemmock.side_effect = phone_modem.exceptions.SerialError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_import(hass):
    """Test import step."""
    with _patch_config_flow_modem(AsyncMock()), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["data"] == CONF_DATA


async def test_flow_import_duplicate(hass):
    """Test already configured import."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: DEFAULT_DEVICE},
    )

    entry.add_to_hass(hass)

    service_info = {"device": DEFAULT_DEVICE}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
