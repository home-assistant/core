"""Test the Yeelight config flow."""
from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.yeelight import (
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
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant

from . import (
    ID,
    IP_ADDRESS,
    MODULE,
    MODULE_CONFIG_FLOW,
    NAME,
    UNIQUE_NAME,
    _mocked_bulb,
    _patch_discovery,
)

from tests.common import MockConfigEntry

DEFAULT_CONFIG = {
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result2["type"] == "form"
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with patch(f"{MODULE}.async_setup", return_value=True) as mock_setup, patch(
        f"{MODULE}.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: ID}
        )
    assert result3["type"] == "create_entry"
    assert result3["title"] == UNIQUE_NAME
    assert result3["data"] == {CONF_ID: ID}
    await hass.async_block_till_done()
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(f"{MODULE_CONFIG_FLOW}.yeelight"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_discovery_no_device(hass: HomeAssistant):
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_discovery(f"{MODULE_CONFIG_FLOW}.yeelight", no_device=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_import(hass: HomeAssistant):
    """Test import from yaml."""
    config = {
        CONF_NAME: DEFAULT_NAME,
        CONF_HOST: IP_ADDRESS,
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
    type(mocked_bulb).get_properties.assert_called_once()
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"

    # Success
    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
    type(mocked_bulb).get_capabilities.assert_called_once()
    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_HOST: IP_ADDRESS,
        CONF_TRANSITION: DEFAULT_TRANSITION,
        CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
        CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
        CONF_NIGHTLIGHT_SWITCH: True,
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
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    # Cannot connect (error)
    type(mocked_bulb).get_capabilities = MagicMock(side_effect=OSError)
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
    assert result3["errors"] == {"base": "cannot_connect"}

    # Success
    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(
        f"{MODULE}.async_setup_entry",
        return_value=True,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()
    assert result4["type"] == "create_entry"
    assert result4["title"] == IP_ADDRESS
    assert result4["data"] == {CONF_HOST: IP_ADDRESS}

    # Duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_options(hass: HomeAssistant):
    """Test options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS, CONF_NAME: NAME}
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    config = {
        CONF_NAME: NAME,
        CONF_MODEL: "",
        CONF_TRANSITION: DEFAULT_TRANSITION,
        CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
        CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
        CONF_NIGHTLIGHT_SWITCH: DEFAULT_NIGHTLIGHT_SWITCH,
    }
    assert config_entry.options == config
    assert hass.states.get(f"light.{NAME}_nightlight") is None

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    config[CONF_NIGHTLIGHT_SWITCH] = True
    user_input = {**config}
    user_input.pop(CONF_NAME)
    with patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()
    assert result2["type"] == "create_entry"
    assert result2["data"] == config
    assert result2["data"] == config_entry.options
    assert hass.states.get(f"light.{NAME}_nightlight") is not None


async def test_manual_no_capabilities(hass: HomeAssistant):
    """Test manually setup without successful get_capabilities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    mocked_bulb = _mocked_bulb()
    type(mocked_bulb).get_capabilities = MagicMock(return_value=None)
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(
        f"{MODULE}.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
    type(mocked_bulb).get_capabilities.assert_called_once()
    type(mocked_bulb).get_properties.assert_called_once()
    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
