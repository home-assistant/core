"""Test the tplink config flow."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.tplink import (
    DOMAIN,
    AuthenticationException,
    Credentials,
    SmartDeviceException,
)
from homeassistant.components.tplink.const import CONF_DEVICE_CONFIG
from homeassistant.const import (
    CONF_ALIAS,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    ALIAS,
    CREATE_ENTRY_DATA_AUTH,
    CREATE_ENTRY_DATA_LEGACY,
    DEFAULT_ENTRY_TITLE,
    DEVICE_CONFIG_DICT_LEGACY,
    IP_ADDRESS,
    MAC_ADDRESS,
    MODULE,
    _patch_connect,
    _patch_discovery,
    _patch_single_discovery,
)

from tests.common import MockConfigEntry


async def test_discovery(hass: HomeAssistant) -> None:
    """Test setting up discovery."""
    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
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

    with _patch_discovery(), _patch_single_discovery(), _patch_connect(), patch(
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
    assert result3["data"] == CREATE_ENTRY_DATA_LEGACY
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_discovery_auth(
    hass: HomeAssistant, mock_discovery: AsyncMock, mock_connect: AsyncMock, mock_init
) -> None:
    """Test setting up discovery."""

    mock_discovery["mock_device"].update.side_effect = AuthenticationException

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: IP_ADDRESS,
            CONF_MAC: MAC_ADDRESS,
            CONF_ALIAS: ALIAS,
            CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_LEGACY,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "discovery_auth_confirm"
    assert not result["errors"]

    mock_discovery["mock_device"].update.reset_mock(side_effect=True)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "discovery_confirm"
    assert not result2["errors"]

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], user_input={}
    )

    await hass.async_block_till_done()
    assert result3["type"] == "create_entry"
    assert result3["title"] == DEFAULT_ENTRY_TITLE
    assert result3["data"] == CREATE_ENTRY_DATA_AUTH


async def test_discovery_with_existing_device_present(hass: HomeAssistant) -> None:
    """Test setting up discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.2"}, unique_id="dd:dd:dd:dd:dd:dd"
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_single_discovery(no_device=True), _patch_connect(
        no_device=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
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

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with _patch_discovery(), _patch_single_discovery(), _patch_connect(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: MAC_ADDRESS}
        )
        assert result3["type"] == "create_entry"
        assert result3["title"] == DEFAULT_ENTRY_TITLE
        assert result3["data"] == CREATE_ENTRY_DATA_LEGACY
        await hass.async_block_till_done()

    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_discovery_no_device(hass: HomeAssistant) -> None:
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_discovery(no_device=True), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"


async def test_manual(hass: HomeAssistant) -> None:
    """Test manually setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Cannot connect (timeout)
    with _patch_discovery(no_device=True), _patch_single_discovery(
        no_device=True
    ), _patch_connect(no_device=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    # Success
    with _patch_discovery(), _patch_single_discovery(), _patch_connect(), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(f"{MODULE}.async_setup_entry", return_value=True):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()
    assert result4["type"] == "create_entry"
    assert result4["title"] == DEFAULT_ENTRY_TITLE
    assert result4["data"] == CREATE_ENTRY_DATA_LEGACY

    # Duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_discovery(no_device=True), _patch_single_discovery(
        no_device=True
    ), _patch_connect(no_device=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_manual_no_capabilities(hass: HomeAssistant) -> None:
    """Test manually setup without successful get_capabilities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(
        no_device=True
    ), _patch_single_discovery(), _patch_connect(), patch(
        f"{MODULE}.async_setup", return_value=True
    ), patch(f"{MODULE}.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["data"] == CREATE_ENTRY_DATA_LEGACY


async def test_manual_auth(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    mock_init,
) -> None:
    """Test manually setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_discovery["mock_device"].update.side_effect = AuthenticationException

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: IP_ADDRESS}
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "user_auth_confirm"
    assert not result2["errors"]

    mock_discovery["mock_device"].update.reset_mock(side_effect=True)

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] == "create_entry"
    assert result3["title"] == DEFAULT_ENTRY_TITLE
    assert result3["data"] == CREATE_ENTRY_DATA_AUTH


async def test_discovered_by_discovery_and_dhcp(hass: HomeAssistant) -> None:
    """Test we get the form with discovery and abort for dhcp source when we get both."""

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                CONF_HOST: IP_ADDRESS,
                CONF_MAC: MAC_ADDRESS,
                CONF_ALIAS: ALIAS,
                CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_LEGACY,
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress=MAC_ADDRESS, hostname=ALIAS
            ),
        )
        await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip=IP_ADDRESS, macaddress="00:00:00:00:00:00", hostname="mock_hostname"
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "already_in_progress"

    with _patch_discovery(no_device=True), _patch_single_discovery(
        no_device=True
    ), _patch_connect(no_device=True):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.2.3.5", macaddress="00:00:00:00:00:01", hostname="mock_hostname"
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (
            config_entries.SOURCE_DHCP,
            dhcp.DhcpServiceInfo(ip=IP_ADDRESS, macaddress=MAC_ADDRESS, hostname=ALIAS),
        ),
        (
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            {
                CONF_HOST: IP_ADDRESS,
                CONF_MAC: MAC_ADDRESS,
                CONF_ALIAS: ALIAS,
                CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_LEGACY,
            },
        ),
    ],
)
async def test_discovered_by_dhcp_or_discovery(
    hass: HomeAssistant, source, data
) -> None:
    """Test we can setup when discovered from dhcp or discovery."""

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_single_discovery(), _patch_connect(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == CREATE_ENTRY_DATA_LEGACY
    assert mock_async_setup.called
    assert mock_async_setup_entry.called


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (
            config_entries.SOURCE_DHCP,
            dhcp.DhcpServiceInfo(ip=IP_ADDRESS, macaddress=MAC_ADDRESS, hostname=ALIAS),
        ),
        (
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            {
                CONF_HOST: IP_ADDRESS,
                CONF_MAC: MAC_ADDRESS,
                CONF_ALIAS: ALIAS,
                CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_LEGACY,
            },
        ),
    ],
)
async def test_discovered_by_dhcp_or_discovery_failed_to_get_device(
    hass: HomeAssistant, source, data
) -> None:
    """Test we abort if we cannot get the unique id when discovered from dhcp."""

    with _patch_discovery(no_device=True), _patch_single_discovery(
        no_device=True
    ), _patch_connect(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_reauth(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
) -> None:
    """Test reauth flow."""
    mock_added_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    assert mock_added_config_entry.state == config_entries.ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
    credentials = Credentials("fake_username", "fake_password")
    mock_discovery["discover_single"].assert_called_once_with(
        "127.0.0.1", credentials=credentials
    )
    mock_discovery["mock_device"].update.assert_called_once_with()
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("error_type", "errors_msg"),
    [
        (AuthenticationException, "invalid_auth"),
        (SmartDeviceException, "unknown"),
    ],
    ids=["invalid-auth", "unknown-error"],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    error_type,
    errors_msg,
) -> None:
    """Test reauth errors."""
    mock_added_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    assert mock_added_config_entry.state == config_entries.ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    mock_discovery["mock_device"].update.side_effect = error_type
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
    credentials = Credentials("fake_username", "fake_password")

    mock_discovery["discover_single"].assert_called_once_with(
        "127.0.0.1", credentials=credentials
    )
    mock_discovery["mock_device"].update.assert_called_once_with()
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": errors_msg}

    mock_discovery["discover_single"].reset_mock()
    mock_discovery["mock_device"].update.reset_mock(side_effect=True)
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )

    mock_discovery["discover_single"].assert_called_once_with(
        "127.0.0.1", credentials=credentials
    )
    mock_discovery["mock_device"].update.assert_called_once_with()

    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
