"""Test the Yeelight config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
from homeassistant.components.yeelight.config_flow import MODEL_UNKNOWN, CannotConnect
from homeassistant.components.yeelight.const import (
    CONF_DETECTED_MODEL,
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
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_FORM

from . import (
    CAPABILITIES,
    ID,
    IP_ADDRESS,
    MODEL,
    MODULE,
    MODULE_CONFIG_FLOW,
    NAME,
    UNIQUE_FRIENDLY_NAME,
    ZEROCONF_DATA,
    _mocked_bulb,
    _patch_discovery,
    _patch_discovery_interval,
    _patch_discovery_timeout,
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
    with _patch_discovery(), _patch_discovery_interval():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result2["type"] == "form"
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

        # test we can try again
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result2["type"] == "form"
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: ID}
        )
    assert result3["type"] == "create_entry"
    assert result3["title"] == UNIQUE_FRIENDLY_NAME
    assert result3["data"] == {CONF_ID: ID, CONF_HOST: IP_ADDRESS, CONF_MODEL: MODEL}
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

    with _patch_discovery(), _patch_discovery_interval():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_discovery_with_existing_device_present(hass: HomeAssistant):
    """Test setting up discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ID: "0x000000000099999", CONF_HOST: "4.4.4.4"}
    )
    config_entry.add_to_hass(hass)
    alternate_bulb = _mocked_bulb()
    alternate_bulb.capabilities["id"] = "0x000000000099999"
    alternate_bulb.capabilities["location"] = "yeelight://4.4.4.4"

    with _patch_discovery(), patch(f"{MODULE}.AsyncBulb", return_value=alternate_bulb):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_discovery_interval():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    # Now abort and make sure we can start over

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_discovery_interval():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] == "form"
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.AsyncBulb", return_value=_mocked_bulb()
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: ID}
        )
        assert result3["type"] == "create_entry"
        assert result3["title"] == UNIQUE_FRIENDLY_NAME
        assert result3["data"] == {
            CONF_ID: ID,
            CONF_HOST: IP_ADDRESS,
            CONF_MODEL: MODEL,
        }
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_discovery_interval():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_discovery_no_device(hass: HomeAssistant):
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_discovery(
        no_device=True
    ), _patch_discovery_timeout(), _patch_discovery_interval():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

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
    with _patch_discovery(
        no_device=True
    ), _patch_discovery_timeout(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"

    # Success
    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ), patch(f"{MODULE}.async_setup", return_value=True) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
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
    with _patch_discovery(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
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
    with _patch_discovery(
        no_device=True
    ), _patch_discovery_timeout(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    # Cannot connect (error)
    with _patch_discovery(
        no_device=True
    ), _patch_discovery_timeout(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
    assert result3["errors"] == {"base": "cannot_connect"}

    # Success
    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_timeout(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ), patch(f"{MODULE}.async_setup", return_value=True), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()
    assert result4["type"] == "create_entry"
    assert result4["title"] == "Color 0x15243f"
    assert result4["data"] == {
        CONF_HOST: IP_ADDRESS,
        CONF_ID: "0x000000000015243f",
        CONF_MODEL: MODEL,
    }

    # Duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mocked_bulb = _mocked_bulb()
    with _patch_discovery(
        no_device=True
    ), _patch_discovery_timeout(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_options(hass: HomeAssistant):
    """Test options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: NAME, CONF_DETECTED_MODEL: MODEL},
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    config = {
        CONF_NAME: NAME,
        CONF_MODEL: MODEL,
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
    user_input.pop(CONF_MODEL)
    with _patch_discovery(), patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()
    assert result2["type"] == "create_entry"
    assert result2["data"] == config
    assert result2["data"] == config_entry.options
    assert hass.states.get(f"light.{NAME}_nightlight") is not None


async def test_options_unknown_model(hass: HomeAssistant):
    """Test options flow with an unknown model."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: NAME, CONF_DETECTED_MODEL: "not_in_db"},
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    config = {
        CONF_NAME: NAME,
        CONF_MODEL: "not_in_db",
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
    with _patch_discovery(), patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb):
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
    with _patch_discovery(
        no_device=True
    ), _patch_discovery_timeout(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_HOST: IP_ADDRESS,
        CONF_ID: None,
        CONF_MODEL: MODEL_UNKNOWN,
    }


async def test_discovered_by_homekit_and_dhcp(hass):
    """Test we get the form with homekit and abort for dhcp source when we get both."""

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=zeroconf.ZeroconfServiceInfo(
                host=IP_ADDRESS,
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={zeroconf.ATTR_PROPERTIES_ID: "aa:bb:cc:dd:ee:ff"},
                type="mock_type",
            ),
        )
        await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress="aa:bb:cc:dd:ee:ff", hostname="mock_hostname"
            ),
        )
        await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_in_progress"

    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress="00:00:00:00:00:00", hostname="mock_hostname"
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "already_in_progress"

    with _patch_discovery(
        no_device=True
    ), _patch_discovery_timeout(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", side_effect=CannotConnect
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.2.3.5", macaddress="00:00:00:00:00:01", hostname="mock_hostname"
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    "source, data",
    [
        (
            config_entries.SOURCE_DHCP,
            dhcp.DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress="aa:bb:cc:dd:ee:ff", hostname="mock_hostname"
            ),
        ),
        (
            config_entries.SOURCE_HOMEKIT,
            zeroconf.ZeroconfServiceInfo(
                host=IP_ADDRESS,
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={zeroconf.ATTR_PROPERTIES_ID: "aa:bb:cc:dd:ee:ff"},
                type="mock_type",
            ),
        ),
    ],
)
async def test_discovered_by_dhcp_or_homekit(hass, source, data):
    """Test we can setup when discovered from dhcp or homekit."""

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        CONF_HOST: IP_ADDRESS,
        CONF_ID: "0x000000000015243f",
        CONF_MODEL: MODEL,
    }
    assert mock_async_setup.called
    assert mock_async_setup_entry.called

    with _patch_discovery(
        no_device=True
    ), _patch_discovery_timeout(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", side_effect=CannotConnect
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()
    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "already_configured"


@pytest.mark.parametrize(
    "source, data",
    [
        (
            config_entries.SOURCE_DHCP,
            dhcp.DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress="aa:bb:cc:dd:ee:ff", hostname="mock_hostname"
            ),
        ),
        (
            config_entries.SOURCE_HOMEKIT,
            zeroconf.ZeroconfServiceInfo(
                host=IP_ADDRESS,
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={zeroconf.ATTR_PROPERTIES_ID: "aa:bb:cc:dd:ee:ff"},
                type="mock_type",
            ),
        ),
    ],
)
async def test_discovered_by_dhcp_or_homekit_failed_to_get_id(hass, source, data):
    """Test we abort if we cannot get the unique id when discovered from dhcp or homekit."""

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(
        no_device=True
    ), _patch_discovery_timeout(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


async def test_discovered_ssdp(hass):
    """Test we can setup when discovered from ssdp."""

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=CAPABILITIES
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        CONF_HOST: IP_ADDRESS,
        CONF_ID: "0x000000000015243f",
        CONF_MODEL: MODEL,
    }
    assert mock_async_setup.called
    assert mock_async_setup_entry.called

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=CAPABILITIES
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_discovered_zeroconf(hass):
    """Test we can setup when discovered from zeroconf."""

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        CONF_HOST: IP_ADDRESS,
        CONF_ID: "0x000000000015243f",
        CONF_MODEL: MODEL,
    }
    assert mock_async_setup.called
    assert mock_async_setup_entry.called

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE_CONFIG_FLOW}.AsyncBulb", return_value=mocked_bulb
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=CAPABILITIES,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
