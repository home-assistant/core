"""Define tests for the Flux LED/Magic Home config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.flux_led.const import (
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    DOMAIN,
    MODE_RGB,
    TRANSITION_JUMP,
    TRANSITION_STROBE,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODE,
    CONF_NAME,
    CONF_PROTOCOL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_FORM

from . import (
    DEFAULT_ENTRY_TITLE,
    DEFAULT_ENTRY_TITLE_PARTIAL,
    DHCP_DISCOVERY,
    FLUX_DISCOVERY,
    IP_ADDRESS,
    MAC_ADDRESS,
    MODULE,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry


async def test_discovery(hass: HomeAssistant):
    """Test setting up discovery."""
    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
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
        await hass.async_block_till_done()
        assert result2["type"] == "form"
        assert result2["step_id"] == "pick_device"
        assert not result2["errors"]

    with _patch_discovery(), _patch_wifibulb(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: MAC_ADDRESS},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == DEFAULT_ENTRY_TITLE
    assert result3["data"] == {CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE}
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_discovery_with_existing_device_present(hass: HomeAssistant):
    """Test setting up discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.2"}, unique_id="dd:dd:dd:dd:dd:dd"
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb(no_device=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
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

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with _patch_discovery(), _patch_wifibulb(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: MAC_ADDRESS}
        )
        assert result3["type"] == "create_entry"
        assert result3["title"] == DEFAULT_ENTRY_TITLE
        assert result3["data"] == {
            CONF_HOST: IP_ADDRESS,
            CONF_NAME: DEFAULT_ENTRY_TITLE,
        }
        await hass.async_block_till_done()

    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_discovery_no_device(hass: HomeAssistant):
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_discovery(no_device=True), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_import(hass: HomeAssistant):
    """Test import from yaml."""
    config = {
        CONF_HOST: IP_ADDRESS,
        CONF_MAC: MAC_ADDRESS,
        CONF_NAME: "floor lamp",
        CONF_PROTOCOL: "ledenet",
        CONF_MODE: MODE_RGB,
        CONF_CUSTOM_EFFECT_COLORS: "[255,0,0], [0,0,255]",
        CONF_CUSTOM_EFFECT_SPEED_PCT: 30,
        CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_STROBE,
    }

    # Success
    with _patch_discovery(), _patch_wifibulb(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "floor lamp"
    assert result["data"] == {
        CONF_HOST: IP_ADDRESS,
        CONF_NAME: "floor lamp",
        CONF_PROTOCOL: "ledenet",
    }
    assert result["options"] == {
        CONF_MODE: MODE_RGB,
        CONF_CUSTOM_EFFECT_COLORS: "[255,0,0], [0,0,255]",
        CONF_CUSTOM_EFFECT_SPEED_PCT: 30,
        CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_STROBE,
    }
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # Duplicate
    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_manual_working_discovery(hass: HomeAssistant):
    """Test manually setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Cannot connect (timeout)
    with _patch_discovery(no_device=True), _patch_wifibulb(no_device=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    # Success
    with _patch_discovery(), _patch_wifibulb(), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(f"{MODULE}.async_setup_entry", return_value=True):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()
    assert result4["type"] == "create_entry"
    assert result4["title"] == DEFAULT_ENTRY_TITLE
    assert result4["data"] == {CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE}

    # Duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_discovery(no_device=True), _patch_wifibulb(no_device=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_manual_no_discovery_data(hass: HomeAssistant):
    """Test manually setup without discovery data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(no_device=True), _patch_wifibulb(), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(f"{MODULE}.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_NAME: IP_ADDRESS}


async def test_discovered_by_discovery_and_dhcp(hass):
    """Test we get the form with discovery and abort for dhcp source when we get both."""

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DISCOVERY},
            data=FLUX_DISCOVERY,
        )
        await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_in_progress"

    with _patch_discovery(), _patch_wifibulb():
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="any",
                ip=IP_ADDRESS,
                macaddress="00:00:00:00:00:00",
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "already_in_progress"


async def test_discovered_by_discovery(hass):
    """Test we can setup when discovered from discovery."""

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DISCOVERY},
            data=FLUX_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_wifibulb(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == {CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE}
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


async def test_discovered_by_dhcp_udp_responds(hass):
    """Test we can setup when discovered from dhcp but with udp response."""

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_wifibulb(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == {CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE}
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


async def test_discovered_by_dhcp_no_udp_response(hass):
    """Test we can setup when discovered from dhcp but no udp response."""

    with _patch_discovery(no_device=True), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with _patch_discovery(no_device=True), _patch_wifibulb(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        CONF_HOST: IP_ADDRESS,
        CONF_NAME: DEFAULT_ENTRY_TITLE_PARTIAL,
    }
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


async def test_discovered_by_dhcp_no_udp_response_or_tcp_response(hass):
    """Test we can setup when discovered from dhcp but no udp response or tcp response."""

    with _patch_discovery(no_device=True), _patch_wifibulb(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    "source, data",
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_DISCOVERY, FLUX_DISCOVERY),
    ],
)
async def test_discovered_by_dhcp_or_discovery_adds_missing_unique_id(
    hass, source, data
):
    """Test we can setup when discovered from dhcp or discovery."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: IP_ADDRESS})
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == MAC_ADDRESS


async def test_options(hass: HomeAssistant):
    """Test options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        options={
            CONF_MODE: MODE_RGB,
            CONF_CUSTOM_EFFECT_COLORS: "[255,0,0], [0,0,255]",
            CONF_CUSTOM_EFFECT_SPEED_PCT: 30,
            CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_STROBE,
        },
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_wifibulb():
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    user_input = {
        CONF_CUSTOM_EFFECT_COLORS: "[0,0,255], [255,0,0]",
        CONF_CUSTOM_EFFECT_SPEED_PCT: 50,
        CONF_CUSTOM_EFFECT_TRANSITION: TRANSITION_JUMP,
    }
    with _patch_discovery(), _patch_wifibulb():
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()
    assert result2["type"] == "create_entry"
    assert result2["data"] == user_input
    assert result2["data"] == config_entry.options
    assert hass.states.get("light.rgbw_controller_ddeeff") is not None
