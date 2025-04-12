"""Test the Powerfox config flow."""

from unittest.mock import AsyncMock, patch

from powerfox import PowerfoxAuthenticationError, PowerfoxConnectionError
import pytest

from homeassistant.components.powerfox.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import MOCK_DIRECT_HOST

from tests.common import MockConfigEntry

MOCK_ZEROCONF_DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=MOCK_DIRECT_HOST,
    ip_addresses=[MOCK_DIRECT_HOST],
    hostname="powerfox.local",
    name="Powerfox",
    port=443,
    type="_http._tcp",
    properties={},
)


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert not result.get("errors")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@powerfox.test", CONF_PASSWORD: "test-password"},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "test@powerfox.test"
    assert result.get("data") == {
        CONF_EMAIL: "test@powerfox.test",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_powerfox_client.all_devices.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert not result.get("errors")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@powerfox.test", CONF_PASSWORD: "test-password"},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "test@powerfox.test"
    assert result.get("data") == {
        CONF_EMAIL: "test@powerfox.test",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_powerfox_client.all_devices.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_powerfox_client: AsyncMock,
) -> None:
    """Test abort when setting up duplicate entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@powerfox.test", CONF_PASSWORD: "test-password"},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_duplicate_entry_reconfiguration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_powerfox_client: AsyncMock,
) -> None:
    """Test abort when setting up duplicate entry on reconfiguration."""
    # Add two config entries
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "new@powerfox.test", CONF_PASSWORD: "new-password"},
    )
    mock_config_entry_2.add_to_hass(hass)
    assert len(hass.config_entries.async_entries()) == 2

    # Reconfigure the second entry
    result = await mock_config_entry_2.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@powerfox.test", CONF_PASSWORD: "test-password"},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (PowerfoxConnectionError, "cannot_connect"),
        (PowerfoxAuthenticationError, "invalid_auth"),
    ],
)
async def test_exceptions(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test exceptions during config flow."""
    mock_powerfox_client.all_devices.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@powerfox.test", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": error}

    # Recover from error
    mock_powerfox_client.all_devices.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@powerfox.test", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_step_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test re-authentication flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    with patch(
        "homeassistant.components.powerfox.config_flow.Powerfox",
        autospec=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "new-password"},
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (PowerfoxConnectionError, "cannot_connect"),
        (PowerfoxAuthenticationError, "invalid_auth"),
    ],
)
async def test_step_reauth_exceptions(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test exceptions during re-authentication flow."""
    mock_powerfox_client.all_devices.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-password"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": error}

    # Recover from error
    mock_powerfox_client.all_devices.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-password"},
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration of existing entry."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "new-email@powerfox.test",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert mock_config_entry.data[CONF_EMAIL] == "new-email@powerfox.test"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (PowerfoxConnectionError, "cannot_connect"),
        (PowerfoxAuthenticationError, "invalid_auth"),
    ],
)
async def test_reconfigure_exceptions(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test exceptions during reconfiguration flow."""
    mock_powerfox_client.all_devices.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "new-email@powerfox.test",
            CONF_PASSWORD: "new-password",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": error}

    # Recover from error
    mock_powerfox_client.all_devices.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "new-email@powerfox.test",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert mock_config_entry.data[CONF_EMAIL] == "new-email@powerfox.test"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
