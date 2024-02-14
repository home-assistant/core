"""Test Netgear LTE config flow."""
from unittest.mock import patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.netgear_lte.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant

from .conftest import CONF_DATA


def _patch_setup():
    return patch(
        "homeassistant.components.netgear_lte.async_setup_entry", return_value=True
    )


async def test_flow_user_form(hass: HomeAssistant, connection: None) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with _patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Netgear LM1200"
    assert result["data"] == CONF_DATA
    assert result["context"]["unique_id"] == "FFFFFFFFFFFFF"


@pytest.mark.parametrize("source", (SOURCE_USER, SOURCE_IMPORT))
async def test_flow_already_configured(
    hass: HomeAssistant, setup_integration: None, source: str
) -> None:
    """Test config flow aborts when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: source},
        data=CONF_DATA,
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_cannot_connect(
    hass: HomeAssistant, cannot_connect: None
) -> None:
    """Test connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONF_DATA,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


async def test_flow_user_unknown_error(hass: HomeAssistant, unknown: None) -> None:
    """Test unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_DATA,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "unknown"


async def test_flow_import(hass: HomeAssistant, connection: None) -> None:
    """Test import step."""
    with _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_IMPORT},
            data=CONF_DATA,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Netgear LM1200"
    assert result["data"] == CONF_DATA


async def test_flow_import_failure(hass: HomeAssistant, cannot_connect: None) -> None:
    """Test import step failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_IMPORT},
        data=CONF_DATA,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"
