"""Test Netgear LTE config flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.netgear_lte.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SOURCE, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CONF_DATA, HOST

from tests.common import async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with _patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Netgear LM1200"
    assert result["data"] == CONF_DATA
    assert result["context"]["unique_id"] == "FFFFFFFFFFFFF"


async def test_flow_already_configured(
    hass: HomeAssistant, setup_integration: None
) -> None:
    """Test config flow aborts when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONF_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("cannot_connect")
async def test_flow_user_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONF_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"http://{HOST}/model.json",
        text=await async_load_fixture(hass, "model.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.post(
        f"http://{HOST}/Forms/config",
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    with _patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
