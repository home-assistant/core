"""Test the WiZ Platform config flow."""
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.wiz.config_flow import (
    WizLightConnectionError,
    WizLightTimeOutError,
)
from homeassistant.components.wiz.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

FAKE_MAC = "ABCABCABCABC"
FAKE_BULB_CONFIG = {
    "method": "getSystemConfig",
    "env": "pro",
    "result": {
        "mac": FAKE_MAC,
        "homeId": 653906,
        "roomId": 989983,
        "moduleName": "ESP_0711_STR",
        "fwVersion": "1.21.0",
        "groupId": 0,
        "drvConf": [20, 2],
        "ewf": [255, 0, 255, 255, 0, 0, 0],
        "ewfHex": "ff00ffff000000",
        "ping": 0,
    },
}
FAKE_EXTENDED_WHITE_RANGE = [2200, 2700, 6500, 6500]
TEST_SYSTEM_INFO = {"id": FAKE_MAC, "name": "Test Bulb"}
TEST_CONNECTION = {CONF_HOST: "1.1.1.1"}
TEST_NO_IP = {CONF_HOST: "this is no IP input"}


def _patch_wizlight():
    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.wiz.wizlight.getBulbConfig",
            return_value=FAKE_BULB_CONFIG,
        ), patch(
            "homeassistant.components.wiz.wizlight.getExtendedWhiteRange",
            return_value=FAKE_EXTENDED_WHITE_RANGE,
        ), patch(
            "homeassistant.components.wiz.wizlight.getMac",
            return_value=FAKE_MAC,
        ):
            yield

    return _patcher()


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # Patch functions
    with _patch_wizlight(), patch(
        "homeassistant.components.wiz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "WiZ Dimmable White ABCABC"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "side_effect, error_base",
    [
        (WizLightTimeOutError, "bulb_time_out"),
        (WizLightConnectionError, "no_wiz_light"),
        (Exception, "unknown"),
        (ConnectionRefusedError, "cannot_connect"),
    ],
)
async def test_user_form_exceptions(hass, side_effect, error_base):
    """Test all user exceptions in the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wiz.wizlight.getBulbConfig",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": error_base}


async def test_form_updates_unique_id(hass):
    """Test a duplicate id aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SYSTEM_INFO["id"],
        data={
            CONF_HOST: "dummy",
        },
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_wizlight(), patch(
        "homeassistant.components.wiz.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
