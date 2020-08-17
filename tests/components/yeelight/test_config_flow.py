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
from homeassistant.components.yeelight.config_flow import TYPE_DISCOVERY, TYPE_MANUAL
from homeassistant.const import CONF_DISCOVERY, CONF_IP_ADDRESS, CONF_NAME, CONF_TYPE
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
from tests.common import MockConfigEntry


async def test_discovery(hass: HomeAssistant):
    """Test setting up discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: TYPE_DISCOVERY},
    )
    assert result2["type"] == "form"
    assert result2["step_id"] == "discovery_setup"
    assert result2["errors"] is None

    with _patch_discovery(f"{MODULE_CONFIG_FLOW}.yeelight"), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result3["type"] == "create_entry"
    assert result3["title"] == "Discovery"
    assert result3["data"] == {CONF_DISCOVERY: True}
    await hass.async_block_till_done()
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # Go directly to manual when discovery is set
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "manual"


async def test_discovery_no_device(hass: HomeAssistant):
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: TYPE_DISCOVERY},
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
    assert result["title"] == IP_ADDRESS
    assert result["data"] == {
        CONF_DISCOVERY: False,
        CONF_NAME: DEFAULT_NAME,
        CONF_IP_ADDRESS: IP_ADDRESS,
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
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: TYPE_MANUAL}
    )
    assert result2["type"] == "form"
    assert result2["step_id"] == "manual"
    assert result2["errors"] == {}

    # Cannot connect (timeout)
    mocked_bulb = _mocked_bulb(cannot_connect=True)
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: IP_ADDRESS}
        )
    assert result3["type"] == "form"
    assert result3["step_id"] == "manual"
    assert result3["errors"] == {"base": "cannot_connect"}

    # Cannot connect (Error)
    type(mocked_bulb).get_capabilities = MagicMock(side_effect=OSError)
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: IP_ADDRESS}
        )
    assert result3["errors"] == {"base": "cannot_connect"}

    # Success
    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(
        f"{MODULE}.async_setup_entry", return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: IP_ADDRESS}
        )
    assert result3["type"] == "create_entry"
    assert result3["data"] == {
        CONF_DISCOVERY: False,
        CONF_IP_ADDRESS: IP_ADDRESS,
    }

    # Duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: TYPE_MANUAL}
    )
    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: IP_ADDRESS}
        )
    assert result3["type"] == "abort"
    assert result3["reason"] == "already_configured"


async def test_option_discovery(hass: HomeAssistant):
    """Test option flow for discovery entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_DISCOVERY: True})
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(MODULE), patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    config = {
        CONF_MODEL: "",
        CONF_TRANSITION: DEFAULT_TRANSITION,
        CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
        CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
        CONF_NIGHTLIGHT_SWITCH: DEFAULT_NIGHTLIGHT_SWITCH,
    }
    assert config_entry.options == {ID: config}
    assert hass.states.get(f"light.{NAME}_nightlight") is None

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "device"
    device = f"{NAME} ({ID})"
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEVICE: device}
    )
    assert result2["type"] == "form"
    assert result2["step_id"] == "options"

    config[CONF_NIGHTLIGHT_SWITCH] = True
    with _patch_discovery(MODULE), patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], config
        )
        await hass.async_block_till_done()
    assert result3["type"] == "create_entry"
    assert result3["data"] == {ID: config}
    assert config_entry.options == {ID: config}
    assert hass.states.get(f"light.{NAME}_nightlight") is not None


async def test_option_manual(hass: HomeAssistant):
    """Test option flow for manual setup entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DISCOVERY: False, CONF_IP_ADDRESS: IP_ADDRESS}
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    config = {
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
    with patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], config
        )
        await hass.async_block_till_done()
    assert result2["type"] == "create_entry"
    assert result2["data"] == config
    assert config_entry.options == config
    assert hass.states.get(f"light.{NAME}_nightlight") is not None
