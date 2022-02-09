"""Test the WiZ Platform config flow."""
from unittest.mock import patch

import pytest
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.wiz.config_flow import CONF_DEVICE
from homeassistant.components.wiz.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_FORM

from . import (
    FAKE_BULB_CONFIG,
    FAKE_DIMMABLE_BULB,
    FAKE_EXTENDED_WHITE_RANGE,
    FAKE_IP,
    FAKE_MAC,
    FAKE_RGBW_BULB,
    FAKE_RGBWW_BULB,
    FAKE_SOCKET,
    FAKE_SOCKET_CONFIG,
    TEST_CONNECTION,
    TEST_SYSTEM_INFO,
    _patch_discovery,
    _patch_wizlight,
)

from tests.common import MockConfigEntry

DHCP_DISCOVERY = dhcp.DhcpServiceInfo(
    hostname="wiz_abcabc",
    ip=FAKE_IP,
    macaddress=FAKE_MAC,
)


INTEGRATION_DISCOVERY = {
    "ip_address": FAKE_IP,
    "mac_address": FAKE_MAC,
}


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
    ) as mock_setup_entry, patch(
        "homeassistant.components.wiz.async_setup", return_value=True
    ) as mock_setup:
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
    assert len(mock_setup.mock_calls) == 1
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
        data={CONF_HOST: "dummy"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_wizlight():
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == FAKE_IP


@pytest.mark.parametrize(
    "source, data",
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, INTEGRATION_DISCOVERY),
    ],
)
async def test_discovered_by_dhcp_connection_fails(hass, source, data):
    """Test we abort on connection failure."""
    with patch(
        "homeassistant.components.wiz.wizlight.getBulbConfig",
        side_effect=WizLightTimeOutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    "source, data, device, bulb_type, extended_white_range, name",
    [
        (
            config_entries.SOURCE_DHCP,
            DHCP_DISCOVERY,
            FAKE_BULB_CONFIG,
            FAKE_DIMMABLE_BULB,
            FAKE_EXTENDED_WHITE_RANGE,
            "WiZ Dimmable White ABCABC",
        ),
        (
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            INTEGRATION_DISCOVERY,
            FAKE_BULB_CONFIG,
            FAKE_DIMMABLE_BULB,
            FAKE_EXTENDED_WHITE_RANGE,
            "WiZ Dimmable White ABCABC",
        ),
        (
            config_entries.SOURCE_DHCP,
            DHCP_DISCOVERY,
            FAKE_BULB_CONFIG,
            FAKE_RGBW_BULB,
            FAKE_EXTENDED_WHITE_RANGE,
            "WiZ RGBW Tunable ABCABC",
        ),
        (
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            INTEGRATION_DISCOVERY,
            FAKE_BULB_CONFIG,
            FAKE_RGBW_BULB,
            FAKE_EXTENDED_WHITE_RANGE,
            "WiZ RGBW Tunable ABCABC",
        ),
        (
            config_entries.SOURCE_DHCP,
            DHCP_DISCOVERY,
            FAKE_BULB_CONFIG,
            FAKE_RGBWW_BULB,
            FAKE_EXTENDED_WHITE_RANGE,
            "WiZ RGBWW Tunable ABCABC",
        ),
        (
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            INTEGRATION_DISCOVERY,
            FAKE_BULB_CONFIG,
            FAKE_RGBWW_BULB,
            FAKE_EXTENDED_WHITE_RANGE,
            "WiZ RGBWW Tunable ABCABC",
        ),
        (
            config_entries.SOURCE_DHCP,
            DHCP_DISCOVERY,
            FAKE_SOCKET_CONFIG,
            FAKE_SOCKET,
            None,
            "WiZ Socket ABCABC",
        ),
        (
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            INTEGRATION_DISCOVERY,
            FAKE_SOCKET_CONFIG,
            FAKE_SOCKET,
            None,
            "WiZ Socket ABCABC",
        ),
    ],
)
async def test_discovered_by_dhcp_or_integration_discovery(
    hass, source, data, device, bulb_type, extended_white_range, name
):
    """Test we can configure when discovered from dhcp or discovery."""
    with _patch_wizlight(
        device=device, extended_white_range=extended_white_range, bulb_type=bulb_type
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "discovery_confirm"

    with patch(
        "homeassistant.components.wiz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.wiz.async_setup", return_value=True
    ) as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == name
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "source, data",
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, INTEGRATION_DISCOVERY),
    ],
)
async def test_discovered_by_dhcp_or_integration_discovery_updates_host(
    hass, source, data
):
    """Test dhcp or discovery updates existing host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SYSTEM_INFO["id"],
        data={CONF_HOST: "dummy"},
    )
    entry.add_to_hass(hass)

    with _patch_wizlight():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == FAKE_IP


async def test_setup_via_discovery(hass):
    """Test setting up via discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery():
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

    with _patch_discovery():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with _patch_wizlight(), patch(
        "homeassistant.components.wiz.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.wiz.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: FAKE_MAC},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "WiZ Dimmable White ABCABC"
    assert result3["data"] == {
        CONF_HOST: "1.1.1.1",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_setup_via_discovery_cannot_connect(hass):
    """Test setting up via discovery and we fail to connect to the discovered device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with patch(
        "homeassistant.components.wiz.wizlight.getBulbConfig",
        side_effect=WizLightTimeOutError,
    ), _patch_discovery():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: FAKE_MAC},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "abort"
    assert result3["reason"] == "cannot_connect"
