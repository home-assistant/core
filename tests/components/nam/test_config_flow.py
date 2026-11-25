"""Define tests for the Nettigo Air Monitor config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from nettigo_air_monitor import ApiError, AuthFailedError, CannotGetMacError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.nam.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("10.10.2.3"),
    ip_addresses=[ip_address("10.10.2.3")],
    hostname="mock_hostname",
    name="mock_name",
    port=None,
    properties={},
    type="mock_type",
)
VALID_CONFIG = {"host": "10.10.2.3"}
VALID_AUTH = {"username": "fake_username", "password": "fake_password"}


@pytest.mark.usefixtures("mock_nam_client")
async def test_form_create_entry_without_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the user step without auth works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.2.3"
    assert result["data"]["host"] == "10.10.2.3"
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_create_entry_with_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_nam: MagicMock,
    mock_nam_client: MagicMock,
) -> None:
    """Test that the user step with auth works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_nam.create.side_effect = [
        AuthFailedError("Authorization has failed"),
        mock_nam_client,
    ]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_AUTH,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.2.3"
    assert result["data"]["host"] == "10.10.2.3"
    assert result["data"]["username"] == "fake_username"
    assert result["data"]["password"] == "fake_password"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry", "mock_nam_client")
async def test_reauth_successful(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test starting a reauthentication flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_AUTH,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (AuthFailedError("Auth Error"), "invalid_auth"),
        (TimeoutError, "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_nam_client")
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nam: MagicMock,
    exc: Exception | type[Exception],
    base_error: str,
) -> None:
    """Test the reauth form is shown again on errors and recovers."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_nam.create.side_effect = exc
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_AUTH,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": base_error}

    mock_nam.create.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_AUTH,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (AuthFailedError("Auth Error"), "invalid_auth"),
        (TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_nam_client")
async def test_form_with_auth_errors(
    hass: HomeAssistant,
    mock_nam: MagicMock,
    exc: Exception | type[Exception],
    base_error: str,
) -> None:
    """Test we handle errors when auth is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_nam.create.side_effect = AuthFailedError("Authorization has failed")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    mock_nam.create.side_effect = exc
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_AUTH,
    )

    assert result["errors"] == {"base": base_error}

    mock_nam.create.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_AUTH,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_nam_client")
async def test_form_errors(
    hass: HomeAssistant,
    mock_nam: MagicMock,
    exc: Exception | type[Exception],
    base_error: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_nam.create.side_effect = exc
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_CONFIG,
    )

    assert result["errors"] == {"base": base_error}

    mock_nam.create.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_abort(hass: HomeAssistant, mock_nam: MagicMock) -> None:
    """Test we handle abort after error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_nam.create.side_effect = CannotGetMacError(
        "Cannot get MAC address from device"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_unsupported"


@pytest.mark.usefixtures("mock_nam_client")
async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that errors are shown when duplicates are added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert mock_config_entry.data["host"] == "1.1.1.1"


@pytest.mark.usefixtures("mock_nam_client")
async def test_zeroconf(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DISCOVERY_INFO,
        context={"source": SOURCE_ZEROCONF},
    )
    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert context["title_placeholders"]["host"] == "10.10.2.3"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.2.3"
    assert result["data"] == {"host": "10.10.2.3"}
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_nam_client")
async def test_zeroconf_with_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_nam: MagicMock
) -> None:
    """Test that the zeroconf step with auth works."""
    mock_nam.create.side_effect = AuthFailedError("Auth Error")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DISCOVERY_INFO,
        context={"source": SOURCE_ZEROCONF},
    )
    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {}
    assert context["title_placeholders"]["host"] == "10.10.2.3"

    mock_nam.create.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_AUTH,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.2.3"
    assert result["data"]["host"] == "10.10.2.3"
    assert result["data"]["username"] == "fake_username"
    assert result["data"]["password"] == "fake_password"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_host_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nam: MagicMock
) -> None:
    """Test that errors are shown when host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DISCOVERY_INFO,
        context={"source": SOURCE_ZEROCONF},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_nam.create.assert_not_called()


@pytest.mark.usefixtures("mock_nam_client")
async def test_zeroconf_already_configured_host_changed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the host is updated when a configured device is discovered with a new IP."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=ZeroconfServiceInfo(
            ip_address=ip_address("10.10.2.99"),
            ip_addresses=[ip_address("10.10.2.99")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
        context={"source": SOURCE_ZEROCONF},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "10.10.2.99"


@pytest.mark.parametrize(
    ("exc", "reason"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (CannotGetMacError("Cannot get MAC address from device"), "device_unsupported"),
    ],
)
async def test_zeroconf_errors(
    hass: HomeAssistant, mock_nam: MagicMock, exc: Exception, reason: str
) -> None:
    """Test we handle errors."""
    mock_nam.create.side_effect = exc
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DISCOVERY_INFO,
        context={"source": SOURCE_ZEROCONF},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_setup_entry", "mock_nam_client")
async def test_reconfigure_successful(
    hass: HomeAssistant,
    mock_config_entry_with_auth: MockConfigEntry,
    mock_nam: MagicMock,
) -> None:
    """Test starting a reconfigure flow."""
    mock_config_entry_with_auth.add_to_hass(hass)

    result = await mock_config_entry_with_auth.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "10.10.10.10"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry_with_auth.data == {
        CONF_HOST: "10.10.10.10",
        CONF_USERNAME: "fake_username",
        CONF_PASSWORD: "fake_password",
    }
    options = mock_nam.create.call_args.args[1]
    assert options.host == "10.10.10.10"
    assert options.username == "fake_username"
    assert options.password == "fake_password"


@pytest.mark.usefixtures("mock_setup_entry", "mock_nam_client")
@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (AuthFailedError("Auth Error"), "invalid_auth"),
    ],
)
async def test_reconfigure_not_successful(
    hass: HomeAssistant,
    mock_config_entry_with_auth: MockConfigEntry,
    mock_nam: MagicMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test starting a reconfigure flow but the device probe fails."""
    mock_config_entry_with_auth.add_to_hass(hass)

    result = await mock_config_entry_with_auth.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_nam.create.side_effect = exc
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "10.10.10.10"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": base_error}

    mock_nam.create.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "10.10.10.10"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry_with_auth.data == {
        CONF_HOST: "10.10.10.10",
        CONF_USERNAME: "fake_username",
        CONF_PASSWORD: "fake_password",
    }


@pytest.mark.usefixtures("mock_nam_client")
async def test_reconfigure_not_the_same_device(
    hass: HomeAssistant, mock_config_entry_with_auth: MockConfigEntry
) -> None:
    """Test starting the reconfiguration process, but with a different printer."""
    mock_config_entry_with_auth.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry_with_auth, unique_id="11:22:33:44:55:66"
    )

    result = await mock_config_entry_with_auth.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "10.10.10.10"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "another_device"
