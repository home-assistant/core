"""Test the WiZ Light config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.wiz_light.config_flow import (
    WizLightConnectionError,
    WizLightTimeOutError,
)
from homeassistant.components.wiz_light.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME

from tests.async_mock import patch
from tests.common import MockConfigEntry

FAKE_BULB_CONFIG = '{"method":"getSystemConfig","env":"pro","result":\
    {"mac":"ABCABCABCABC",\
    "homeId":653906,\
    "roomId":989983,\
    "moduleName":"ESP_0711_STR",\
    "fwVersion":"1.21.0",\
    "groupId":0,"drvConf":[20,2],\
    "ewf":[255,0,255,255,0,0,0],\
    "ewfHex":"ff00ffff000000",\
    "ping":0}}'

TEST_SYSTEM_INFO = {"id": "ABCABCABCABC", "name": "Test Bulb"}


TEST_CONNECTION = {CONF_HOST: "1.1.1.1", CONF_NAME: "Test Bulb"}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # Patch booth functions from __init__ with true.
    with patch(
        "homeassistant.components.wiz_light.wizlight.getBulbConfig",
        return_value=FAKE_BULB_CONFIG,
    ), patch(
        "homeassistant.components.wiz_light.wizlight.getMac",
        return_value="ABCABCABCABC",
    ), patch(
        "homeassistant.components.wiz_light.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.wiz_light.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()
    print(result2)
    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test Bulb"
    assert result2["data"] == TEST_CONNECTION
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_bulb_time_out(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wiz_light.wizlight.getBulbConfig",
        side_effect=WizLightTimeOutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "bulb_time_out"}


async def test_form_bulb_offline(hass):
    """Test we handle not a WiZ light error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wiz_light.wizlight.getBulbConfig",
        side_effect=WizLightConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "no_wiz_light"}


async def test_form_bulb_exception(hass):
    """Test we handle a WiZ unknown light error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wiz_light.wizlight.getBulbConfig",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_updates_unique_id(hass):
    """Test a duplicate id aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SYSTEM_INFO["id"],
        data={
            CONF_HOST: "dummy",
            CONF_NAME: TEST_SYSTEM_INFO["name"],
            "id": TEST_SYSTEM_INFO["id"],
        },
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.wiz_light.wizlight.getBulbConfig",
        return_value=FAKE_BULB_CONFIG,
    ), patch(
        "homeassistant.components.wiz_light.wizlight.getMac",
        return_value="ABCABCABCABC",
    ), patch(
        "homeassistant.components.wiz_light.async_setup", return_value=True
    ), patch(
        "homeassistant.components.wiz_light.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "single_instance_allowed"
