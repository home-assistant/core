"""Test the tplink config flow."""
from unittest.mock import AsyncMock, patch

from kasa import TimeoutException
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
    CREATE_ENTRY_DATA_AUTH2,
    CREATE_ENTRY_DATA_LEGACY,
    DEFAULT_ENTRY_TITLE,
    DEVICE_CONFIG_DICT_AUTH,
    DEVICE_CONFIG_DICT_LEGACY,
    IP_ADDRESS,
    MAC_ADDRESS,
    MAC_ADDRESS2,
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
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_discovery_auth(
    hass: HomeAssistant, mock_discovery: AsyncMock, mock_connect: AsyncMock, mock_init
) -> None:
    """Test authenticated discovery."""

    mock_discovery["mock_device"].update.side_effect = AuthenticationException

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: IP_ADDRESS,
            CONF_MAC: MAC_ADDRESS,
            CONF_ALIAS: ALIAS,
            CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH,
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
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == DEFAULT_ENTRY_TITLE
    assert result3["data"] == CREATE_ENTRY_DATA_AUTH


@pytest.mark.parametrize(
    ("error_type", "errors_msg", "error_placement"),
    [
        (AuthenticationException, "invalid_auth", CONF_PASSWORD),
        (SmartDeviceException, "cannot_connect", "base"),
    ],
    ids=["invalid-auth", "unknown-error"],
)
async def test_discovery_auth_errors(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    mock_init,
    error_type,
    errors_msg,
    error_placement,
) -> None:
    """Test handling of discovery authentication errors."""
    mock_discovery["mock_device"].update.side_effect = AuthenticationException
    default_connect_side_effect = mock_connect["connect"].side_effect
    mock_connect["connect"].side_effect = error_type

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: IP_ADDRESS,
            CONF_MAC: MAC_ADDRESS,
            CONF_ALIAS: ALIAS,
            CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "discovery_auth_confirm"
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {error_placement: errors_msg}

    await hass.async_block_till_done()

    mock_connect["connect"].side_effect = default_connect_side_effect
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "discovery_confirm"

    await hass.async_block_till_done()

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {},
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["data"] == CREATE_ENTRY_DATA_AUTH


async def test_discovery_new_credentials(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    mock_init,
) -> None:
    """Test setting up discovery with new credentials."""
    mock_discovery["mock_device"].update.side_effect = AuthenticationException

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: IP_ADDRESS,
            CONF_MAC: MAC_ADDRESS,
            CONF_ALIAS: ALIAS,
            CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "discovery_auth_confirm"
    assert not result["errors"]

    assert mock_connect["connect"].call_count == 0

    with patch(
        "homeassistant.components.tplink.config_flow.get_credentials",
        return_value=Credentials("fake_user", "fake_pass"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )

    assert mock_connect["connect"].call_count == 1
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "discovery_confirm"

    await hass.async_block_till_done()

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {},
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == CREATE_ENTRY_DATA_AUTH


async def test_discovery_new_credentials_invalid(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    mock_init,
) -> None:
    """Test setting up discovery with new invalid credentials."""
    mock_discovery["mock_device"].update.side_effect = AuthenticationException
    default_connect_side_effect = mock_connect["connect"].side_effect

    mock_connect["connect"].side_effect = AuthenticationException

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: IP_ADDRESS,
            CONF_MAC: MAC_ADDRESS,
            CONF_ALIAS: ALIAS,
            CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "discovery_auth_confirm"
    assert not result["errors"]

    assert mock_connect["connect"].call_count == 0

    with patch(
        "homeassistant.components.tplink.config_flow.get_credentials",
        return_value=Credentials("fake_user", "fake_pass"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )

    assert mock_connect["connect"].call_count == 1
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "discovery_auth_confirm"

    await hass.async_block_till_done()

    mock_connect["connect"].side_effect = default_connect_side_effect
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "discovery_confirm"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {},
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["data"] == CREATE_ENTRY_DATA_AUTH


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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    # Now abort and make sure we can start over

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    with _patch_discovery(), _patch_single_discovery(), _patch_connect(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: MAC_ADDRESS}
        )
        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == DEFAULT_ENTRY_TITLE
        assert result3["data"] == CREATE_ENTRY_DATA_LEGACY
        await hass.async_block_till_done()

    mock_setup_entry.assert_called_once()

    # ignore configured devices
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_discovery_no_device(hass: HomeAssistant) -> None:
    """Test discovery without device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_discovery(no_device=True), _patch_single_discovery(), _patch_connect():
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_devices_found"


async def test_manual(hass: HomeAssistant) -> None:
    """Test manually setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.FORM
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
    assert result4["type"] is FlowResultType.CREATE_ENTRY
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

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_manual_no_capabilities(hass: HomeAssistant) -> None:
    """Test manually setup without successful get_capabilities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_discovery["mock_device"].update.side_effect = AuthenticationException

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: IP_ADDRESS}
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
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
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == DEFAULT_ENTRY_TITLE
    assert result3["data"] == CREATE_ENTRY_DATA_AUTH


@pytest.mark.parametrize(
    ("error_type", "errors_msg", "error_placement"),
    [
        (AuthenticationException, "invalid_auth", CONF_PASSWORD),
        (SmartDeviceException, "cannot_connect", "base"),
    ],
    ids=["invalid-auth", "unknown-error"],
)
async def test_manual_auth_errors(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    mock_init,
    error_type,
    errors_msg,
    error_placement,
) -> None:
    """Test manually setup auth errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_discovery["mock_device"].update.side_effect = AuthenticationException
    default_connect_side_effect = mock_connect["connect"].side_effect
    mock_connect["connect"].side_effect = error_type

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: IP_ADDRESS}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user_auth_confirm"
    assert not result2["errors"]

    await hass.async_block_till_done()

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "user_auth_confirm"
    assert result3["errors"] == {error_placement: errors_msg}

    mock_connect["connect"].side_effect = default_connect_side_effect
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["data"] == CREATE_ENTRY_DATA_AUTH

    await hass.async_block_till_done()


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
    assert result["type"] is FlowResultType.FORM
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
    assert result2["type"] is FlowResultType.ABORT
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
    assert result3["type"] is FlowResultType.ABORT
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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with _patch_discovery(), _patch_single_discovery(), _patch_connect(), patch(
        f"{MODULE}.async_setup", return_value=True
    ) as mock_async_setup, patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
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
    assert result["type"] is FlowResultType.ABORT
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
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    await hass.async_block_till_done()


async def test_reauth_update_from_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
) -> None:
    """Test reauth flow."""
    mock_connect["connect"].side_effect = AuthenticationException
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == config_entries.ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"
    assert mock_config_entry.data[CONF_DEVICE_CONFIG] == DEVICE_CONFIG_DICT_LEGACY

    discovery_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: IP_ADDRESS,
            CONF_MAC: MAC_ADDRESS,
            CONF_ALIAS: ALIAS,
            CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH,
        },
    )
    await hass.async_block_till_done()
    assert discovery_result["type"] is FlowResultType.ABORT
    assert discovery_result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_DEVICE_CONFIG] == DEVICE_CONFIG_DICT_AUTH


async def test_reauth_update_from_discovery_with_ip_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
) -> None:
    """Test reauth flow."""
    mock_connect["connect"].side_effect = AuthenticationException()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == config_entries.ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"
    assert mock_config_entry.data[CONF_DEVICE_CONFIG] == DEVICE_CONFIG_DICT_LEGACY

    discovery_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: "127.0.0.2",
            CONF_MAC: MAC_ADDRESS,
            CONF_ALIAS: ALIAS,
            CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH,
        },
    )
    await hass.async_block_till_done()
    assert discovery_result["type"] is FlowResultType.ABORT
    assert discovery_result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_DEVICE_CONFIG] == DEVICE_CONFIG_DICT_AUTH
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.2"


async def test_reauth_no_update_if_config_and_ip_the_same(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
) -> None:
    """Test reauth discovery does not update when the host and config are the same."""
    mock_connect["connect"].side_effect = AuthenticationException()
    mock_config_entry.data = {
        **mock_config_entry.data,
        CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH,
    }
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"
    assert mock_config_entry.data[CONF_DEVICE_CONFIG] == DEVICE_CONFIG_DICT_AUTH

    discovery_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: IP_ADDRESS,
            CONF_MAC: MAC_ADDRESS,
            CONF_ALIAS: ALIAS,
            CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH,
        },
    )
    await hass.async_block_till_done()
    assert discovery_result["type"] is FlowResultType.ABORT
    assert discovery_result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_DEVICE_CONFIG] == DEVICE_CONFIG_DICT_AUTH
    assert mock_config_entry.data[CONF_HOST] == IP_ADDRESS


@pytest.mark.parametrize(
    ("error_type", "errors_msg", "error_placement"),
    [
        (AuthenticationException, "invalid_auth", CONF_PASSWORD),
        (SmartDeviceException, "cannot_connect", "base"),
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
    error_placement,
) -> None:
    """Test reauth errors."""
    mock_added_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    assert mock_added_config_entry.state is config_entries.ConfigEntryState.LOADED
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
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {error_placement: errors_msg}

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

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("error_type", "expected_flow"),
    [
        (AuthenticationException, FlowResultType.FORM),
        (SmartDeviceException, FlowResultType.ABORT),
    ],
    ids=["invalid-auth", "unknown-error"],
)
async def test_pick_device_errors(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    error_type,
    expected_flow,
) -> None:
    """Test errors on pick_device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pick_device"
    assert not result2["errors"]

    default_connect_side_effect = mock_connect["connect"].side_effect
    mock_connect["connect"].side_effect = error_type
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_DEVICE: MAC_ADDRESS},
    )
    await hass.async_block_till_done()
    assert result3["type"] == expected_flow

    if expected_flow != FlowResultType.ABORT:
        mock_connect["connect"].side_effect = default_connect_side_effect
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            user_input={
                CONF_USERNAME: "fake_username",
                CONF_PASSWORD: "fake_password",
            },
        )
        assert result4["type"] == FlowResultType.CREATE_ENTRY


async def test_discovery_timeout_connect(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    mock_init,
) -> None:
    """Test discovery tries legacy connect on timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_discovery["discover_single"].side_effect = TimeoutException
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]
    assert mock_connect["connect"].call_count == 0

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: IP_ADDRESS}
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert mock_connect["connect"].call_count == 1


async def test_reauth_update_other_flows(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    # mock_init,
) -> None:
    """Test reauth updates other reauth flows."""
    mock_config_entry2 = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data={**CREATE_ENTRY_DATA_AUTH2},
        unique_id=MAC_ADDRESS2,
    )
    default_side_effect = mock_connect["connect"].side_effect
    mock_connect["connect"].side_effect = AuthenticationException()
    mock_config_entry.add_to_hass(hass)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry2.state == config_entries.ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.state == config_entries.ConfigEntryState.SETUP_ERROR
    mock_connect["connect"].side_effect = default_side_effect

    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 2
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"
    assert mock_config_entry.data[CONF_DEVICE_CONFIG] == DEVICE_CONFIG_DICT_LEGACY

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
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0
