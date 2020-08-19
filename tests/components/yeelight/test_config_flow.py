"""Test the Yeelight config flow."""
from homeassistant import config_entries
from homeassistant.components.yeelight import (
    CONF_DEVICE,
    CONF_MODE_MUSIC,
    CONF_MODEL,
    CONF_NIGHTLIGHT_SWITCH,
    CONF_NIGHTLIGHT_SWITCH_TYPE,
    CONF_SAVE_ON_CHANGE,
    CONF_TRANSITION,
    DEFAULT_MODE_MUSIC,
    DEFAULT_NAME,
    DEFAULT_NIGHTLIGHT_SWITCH,
    DEFAULT_SAVE_ON_CHANGE,
    DEFAULT_TRANSITION,
    DOMAIN,
    NIGHTLIGHT_SWITCH_TYPE_LIGHT,
)
from homeassistant.const import CONF_ID, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from . import (
    ID,
    IP_ADDRESS,
    MODULE,
    MODULE_CONFIG_FLOW,
    NAME,
    _mocked_bulb,
    _patch_discovery,
)

from tests.async_mock import MagicMock, patch

DEFAULT_CONFIG = {
    CONF_NAME: NAME,
    CONF_MODEL: "",
    CONF_TRANSITION: DEFAULT_TRANSITION,
    CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
    CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
    CONF_NIGHTLIGHT_SWITCH: DEFAULT_NIGHTLIGHT_SWITCH,
}


async def test_discovery(hass: HomeAssistant):
    """Test setting up discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(f"{MODULE_CONFIG_FLOW}.yeelight"):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {},)
        assert result2["type"] == "form"
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: ID}
    )
    assert result3["type"] == "form"
    assert result3["step_id"] == "options"
    assert not result3["errors"]

    with patch(f"{MODULE}.async_setup", return_value=True) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEFAULT_CONFIG
        )

    assert result4["type"] == "create_entry"
    assert result4["title"] == NAME
    assert result4["data"] == {
        **DEFAULT_CONFIG,
        CONF_IP_ADDRESS: "",
        CONF_ID: ID,
    }
    await hass.async_block_till_done()
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()


async def test_discovery_no_device(hass: HomeAssistant):
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_discovery(f"{MODULE_CONFIG_FLOW}.yeelight", no_device=True):
        result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result3["type"] == "abort"
    assert result3["reason"] == "no_devices_found"


async def test_import(hass: HomeAssistant):
    """Test import from yaml."""
    config = {
        CONF_NAME: DEFAULT_NAME,
        CONF_IP_ADDRESS: IP_ADDRESS,
        CONF_TRANSITION: DEFAULT_TRANSITION,
        CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
        CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
        CONF_NIGHTLIGHT_SWITCH_TYPE: NIGHTLIGHT_SWITCH_TYPE_LIGHT,
    }

    # Cannot connect
    mocked_bulb = _mocked_bulb(cannot_connect=True)
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
    type(mocked_bulb).get_capabilities.assert_called_once()
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"

    # Success
    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
    type(mocked_bulb).get_capabilities.assert_called_once()
    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_IP_ADDRESS: IP_ADDRESS,
        CONF_TRANSITION: DEFAULT_TRANSITION,
        CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
        CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
        CONF_NIGHTLIGHT_SWITCH: True,
        CONF_ID: "",
    }
    await hass.async_block_till_done()
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # Duplicate
    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
    type(mocked_bulb).get_capabilities.assert_not_called()
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_manual(hass: HomeAssistant):
    """Test manually setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Cannot connect (timeout)
    mocked_bulb = _mocked_bulb(cannot_connect=True)
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: IP_ADDRESS}
        )
    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    # Cannot connect (Error)
    type(mocked_bulb).get_capabilities = MagicMock(side_effect=OSError)
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: IP_ADDRESS}
        )
    assert result3["errors"] == {"base": "cannot_connect"}

    # Success
    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: IP_ADDRESS}
        )
    assert result4["type"] == "form"
    assert result4["step_id"] == "options"
    assert not result["errors"]

    with patch(f"{MODULE}.async_setup", return_value=True), patch(
        f"{MODULE}.async_setup_entry", return_value=True,
    ):
        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEFAULT_CONFIG
        )
    assert result5["type"] == "create_entry"
    assert result5["data"] == {
        **DEFAULT_CONFIG,
        CONF_IP_ADDRESS: IP_ADDRESS,
        CONF_ID: "",
    }

    # Duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: IP_ADDRESS}
        )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
