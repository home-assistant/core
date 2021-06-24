"""Test Mikrotik setup process."""

import librouteros

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.mikrotik.const import (
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_DHCP_SERVER_TRACK_MODE,
    CONF_USE_DHCP_SERVER,
    DEFAULT_DETECTION_TIME,
    DEFAULT_DHCP_SERVER_TRACK_MODE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_DHCP_SERVER,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.mikrotik import MOCK_DATA
from tests.components.mikrotik.test_hub import setup_mikrotik_entry

DEMO_USER_INPUT = {
    CONF_HOST: "0.0.0.1",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 8278,
    CONF_VERIFY_SSL: False,
}


async def test_flow_works(hass):
    """Test config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_HOST] == "0.0.0.1"
    assert result["data"][CONF_USERNAME] == "username"
    assert result["data"][CONF_PASSWORD] == "password"
    assert result["data"][CONF_PORT] == 8278
    assert result["data"][CONF_VERIFY_SSL] is False


async def test_options(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    await setup_mikrotik_entry(hass, entry)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_tracker"
    assert result["data_schema"]({}) == {
        CONF_USE_DHCP_SERVER: DEFAULT_USE_DHCP_SERVER,
        CONF_DHCP_SERVER_TRACK_MODE: DEFAULT_DHCP_SERVER_TRACK_MODE,
        CONF_DETECTION_TIME: DEFAULT_DETECTION_TIME,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "force_dhcp": False,
            CONF_DHCP_SERVER_TRACK_MODE: "ARP ping",
            CONF_DETECTION_TIME: 200,
            CONF_SCAN_INTERVAL: 10,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "force_dhcp": False,
        CONF_DHCP_SERVER_TRACK_MODE: "ARP ping",
        CONF_DETECTION_TIME: 200,
        CONF_SCAN_INTERVAL: 10,
        CONF_ARP_PING: True,
    }


async def test_options_no_wireless_support(hass: HomeAssistant) -> None:
    """Test updating options when hub doesn't support wireless."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    await setup_mikrotik_entry(
        hass, entry, support_capsman=False, support_wireless=False
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_tracker"
    assert result["data_schema"]({}) == {
        CONF_DHCP_SERVER_TRACK_MODE: DEFAULT_DHCP_SERVER_TRACK_MODE,
        CONF_DETECTION_TIME: DEFAULT_DETECTION_TIME,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DHCP_SERVER_TRACK_MODE: "ARP ping",
            CONF_DETECTION_TIME: 200,
            CONF_SCAN_INTERVAL: 10,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "force_dhcp": DEFAULT_USE_DHCP_SERVER,
        CONF_DHCP_SERVER_TRACK_MODE: "ARP ping",
        CONF_DETECTION_TIME: 200,
        CONF_SCAN_INTERVAL: 10,
        CONF_ARP_PING: True,
    }


async def test_connection_error(hass, mock_api):
    """Test error when connection is unsuccessful."""

    mock_api.side_effect = librouteros.exceptions.ConnectionClosed

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_wrong_credentials(hass: HomeAssistant, mock_api) -> None:
    """Test error when credentials are wrong."""

    mock_api.side_effect = librouteros.exceptions.TrapError(
        "invalid user name or password"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {
        CONF_USERNAME: "invalid_auth",
        CONF_PASSWORD: "invalid_auth",
    }


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_DATA, unique_id=MOCK_DATA[CONF_HOST]
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 8278,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_failed(hass: HomeAssistant, mock_api) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_DATA, unique_id=MOCK_DATA[CONF_HOST]
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    mock_api.side_effect = librouteros.exceptions.TrapError(
        "invalid user name or password"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 8278,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {
        CONF_USERNAME: "invalid_auth",
        CONF_PASSWORD: "invalid_auth",
    }
