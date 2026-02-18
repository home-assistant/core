"""Test the Powerfox Local config flow."""

from unittest.mock import AsyncMock

from powerfox import PowerfoxAuthenticationError, PowerfoxConnectionError
import pytest

from homeassistant.components.powerfox_local.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import MOCK_API_KEY, MOCK_DEVICE_ID, MOCK_HOST

from tests.common import MockConfigEntry

MOCK_ZEROCONF_DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=MOCK_HOST,
    ip_addresses=[MOCK_HOST],
    hostname="powerfox.local",
    name="Powerfox",
    port=443,
    type="_http._tcp",
    properties={"id": MOCK_DEVICE_ID},
)


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_powerfox_local_client: AsyncMock,
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
        user_input={CONF_HOST: MOCK_HOST, CONF_API_KEY: MOCK_API_KEY},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == f"Poweropti ({MOCK_DEVICE_ID[-5:]})"
    assert result.get("data") == {
        CONF_HOST: MOCK_HOST,
        CONF_API_KEY: MOCK_API_KEY,
    }
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert len(mock_powerfox_local_client.value.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_powerfox_local_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == f"Poweropti ({MOCK_DEVICE_ID[-5:]})"
    assert result.get("data") == {
        CONF_HOST: MOCK_HOST,
        CONF_API_KEY: MOCK_API_KEY,
    }
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "exception",
    [
        PowerfoxConnectionError,
        PowerfoxAuthenticationError,
    ],
)
async def test_zeroconf_discovery_errors(
    hass: HomeAssistant,
    mock_powerfox_local_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test zeroconf discovery aborts on connection/auth errors."""
    mock_powerfox_local_client.value.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO,
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


async def test_zeroconf_already_configured(
    hass: HomeAssistant,
    mock_powerfox_local_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf discovery aborts when already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO,
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_powerfox_local_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test abort when setting up duplicate entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: MOCK_HOST, CONF_API_KEY: MOCK_API_KEY},
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
async def test_user_flow_exceptions(
    hass: HomeAssistant,
    mock_powerfox_local_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test exceptions during user config flow."""
    mock_powerfox_local_client.value.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: MOCK_HOST, CONF_API_KEY: MOCK_API_KEY},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": error}

    # Recover from error
    mock_powerfox_local_client.value.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: MOCK_HOST, CONF_API_KEY: MOCK_API_KEY},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
