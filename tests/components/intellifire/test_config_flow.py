"""Test the IntelliFire config flow."""

from unittest.mock import AsyncMock

from intellifire4py.exceptions import LoginError

from homeassistant import config_entries
from homeassistant.components.intellifire.const import (
    API_MODE_CLOUD,
    API_MODE_LOCAL,
    CONF_CONTROL_MODE,
    CONF_READ_MODE,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry


async def test_standard_config_with_single_fireplace(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_apis_single_fp,
) -> None:
    """Test standard flow with a user who has only a single fireplace."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )
    # For a single fireplace we just create it
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "ip_address": "192.168.2.108",
        "api_key": "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
        "serial": "3FB284769E4736F30C8973A7ED358123",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_standard_config_with_pre_configured_fireplace(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry_current,
    mock_apis_single_fp,
) -> None:
    """What if we try to configure an already configured fireplace."""
    # Configure an existing entry
    mock_config_entry_current.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )

    # For a single fireplace we just create it
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_available_devices"


async def test_standard_config_with_single_fireplace_and_bad_credentials(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_apis_single_fp,
) -> None:
    """Test bad credentials on a login."""
    _mock_local_interface, mock_cloud_interface, _mock_fp = mock_apis_single_fp
    # Set login error
    mock_cloud_interface.login_with_credentials.side_effect = LoginError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )

    # Erase the error
    mock_cloud_interface.login_with_credentials.side_effect = None

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_error"}
    assert result["step_id"] == "cloud_api"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )
    # For a single fireplace we just create it
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "ip_address": "192.168.2.108",
        "api_key": "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
        "serial": "3FB284769E4736F30C8973A7ED358123",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_standard_config_with_multiple_fireplace(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_apis_multifp,
) -> None:
    """Test multi-fireplace user who must be very rich."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )
    # When we have multiple fireplaces we get to pick a serial
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_cloud_device"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SERIAL: "4GC295860E5837G40D9974B7FD459234"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "ip_address": "192.168.2.109",
        "api_key": "D4C5EB28BBFF41E1FB21AFF9BFA6CD34",
        "serial": "4GC295860E5837G40D9974B7FD459234",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_dhcp_discovery_intellifire_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_apis_multifp,
) -> None:
    """Test successful DHCP Discovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="aabbcceeddff",
            hostname="zentrios-Test",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_dhcp_discovery_non_intellifire_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_apis_multifp,
) -> None:
    """Test successful DHCP Discovery of a non intellifire device.."""

    # Patch poll with an exception
    mock_local_interface, _mock_cloud_interface, _mock_fp = mock_apis_multifp
    mock_local_interface.poll.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="aabbcceeddff",
            hostname="zentrios-Evil",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_intellifire_device"
    # Test is finished - the DHCP scanner detected a hostname that "might" be an IntelliFire device, but it was not.


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_apis_single_fp,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth."""

    mock_config_entry_current.add_to_hass(hass)
    result = await mock_config_entry_current.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result["step_id"] = "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_apis_single_fp,
) -> None:
    """Test options flow for changing read/control modes."""
    _mock_local, _mock_cloud, mock_fp = mock_apis_single_fp

    mock_config_entry_current.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_current.entry_id)
    await hass.async_block_till_done()

    # Enable both connectivity for this test
    mock_fp.local_connectivity = True
    mock_fp.cloud_connectivity = True

    # Start options flow
    result = await hass.config_entries.options.async_init(
        mock_config_entry_current.entry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Submit new options - both should succeed with connectivity enabled
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_READ_MODE: API_MODE_CLOUD, CONF_CONTROL_MODE: API_MODE_LOCAL},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_READ_MODE: API_MODE_CLOUD,
        CONF_CONTROL_MODE: API_MODE_LOCAL,
    }


async def test_options_flow_local_read_unavailable(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_apis_single_fp,
) -> None:
    """Test options flow shows error when local connectivity unavailable for read mode."""
    _mock_local, _mock_cloud, mock_fp = mock_apis_single_fp

    mock_config_entry_current.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_current.entry_id)
    await hass.async_block_till_done()

    # Disable local connectivity
    mock_fp.local_connectivity = False
    mock_fp.cloud_connectivity = True

    # Start options flow
    result = await hass.config_entries.options.async_init(
        mock_config_entry_current.entry_id
    )

    # Try to select local read mode - should fail
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_READ_MODE: API_MODE_LOCAL, CONF_CONTROL_MODE: API_MODE_CLOUD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_READ_MODE: "local_unavailable"}
    # Verify connectivity was checked
    mock_fp.async_validate_connectivity.assert_called_once()


async def test_options_flow_local_control_unavailable(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_apis_single_fp,
) -> None:
    """Test options flow shows error when local connectivity unavailable for control mode."""
    _mock_local, _mock_cloud, mock_fp = mock_apis_single_fp

    mock_config_entry_current.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_current.entry_id)
    await hass.async_block_till_done()

    # Disable local connectivity
    mock_fp.local_connectivity = False
    mock_fp.cloud_connectivity = True

    # Start options flow
    result = await hass.config_entries.options.async_init(
        mock_config_entry_current.entry_id
    )

    # Try to select local control mode - should fail
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_READ_MODE: API_MODE_CLOUD, CONF_CONTROL_MODE: API_MODE_LOCAL},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_CONTROL_MODE: "local_unavailable"}


async def test_options_flow_cloud_read_unavailable(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_apis_single_fp,
) -> None:
    """Test options flow shows error when cloud connectivity unavailable for read mode."""
    _mock_local, _mock_cloud, mock_fp = mock_apis_single_fp

    mock_config_entry_current.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_current.entry_id)
    await hass.async_block_till_done()

    # Disable cloud connectivity
    mock_fp.local_connectivity = True
    mock_fp.cloud_connectivity = False

    # Start options flow
    result = await hass.config_entries.options.async_init(
        mock_config_entry_current.entry_id
    )

    # Try to select cloud read mode - should fail
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_READ_MODE: API_MODE_CLOUD, CONF_CONTROL_MODE: API_MODE_LOCAL},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_READ_MODE: "cloud_unavailable"}
    # Verify connectivity was checked
    mock_fp.async_validate_connectivity.assert_called_once()


async def test_options_flow_cloud_control_unavailable(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_apis_single_fp,
) -> None:
    """Test options flow shows error when cloud connectivity unavailable for control mode."""
    _mock_local, _mock_cloud, mock_fp = mock_apis_single_fp

    mock_config_entry_current.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_current.entry_id)
    await hass.async_block_till_done()

    # Disable cloud connectivity
    mock_fp.local_connectivity = True
    mock_fp.cloud_connectivity = False

    # Start options flow
    result = await hass.config_entries.options.async_init(
        mock_config_entry_current.entry_id
    )

    # Try to select cloud control mode - should fail
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_READ_MODE: API_MODE_LOCAL, CONF_CONTROL_MODE: API_MODE_CLOUD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_CONTROL_MODE: "cloud_unavailable"}
