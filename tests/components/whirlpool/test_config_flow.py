"""Test the Whirlpool Sixth Sense config flow."""

from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from whirlpool.auth import AccountLockedError

from homeassistant import config_entries
from homeassistant.components.whirlpool.const import CONF_BRAND, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG_INPUT = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


@pytest.fixture(name="mock_whirlpool_setup_entry")
def fixture_mock_whirlpool_setup_entry():
    """Set up async_setup_entry fixture."""
    with patch(
        "homeassistant.components.whirlpool.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.mark.usefixtures("mock_auth_api", "mock_appliances_manager_api")
async def test_form(
    hass: HomeAssistant,
    region,
    brand,
    mock_backend_selector_api: MagicMock,
    mock_whirlpool_setup_entry: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG_INPUT | {"region": region[0], "brand": brand[0]},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "region": region[0],
        "brand": brand[0],
    }
    assert len(mock_whirlpool_setup_entry.mock_calls) == 1
    mock_backend_selector_api.assert_called_once_with(brand[1], region[1])


async def test_form_invalid_auth(
    hass: HomeAssistant, region, brand, mock_auth_api: MagicMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_auth_api.return_value.is_access_token_valid.return_value = False
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG_INPUT | {"region": region[0], "brand": brand[0]},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.usefixtures("mock_appliances_manager_api")
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (AccountLockedError, "account_locked"),
        (aiohttp.ClientConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_auth_error(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
    region,
    brand,
    mock_auth_api: MagicMock,
    mock_whirlpool_setup_entry: MagicMock,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_auth_api.return_value.do_auth.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG_INPUT
        | {
            "region": region[0],
            "brand": brand[0],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Test that it succeeds after the error is cleared
    mock_auth_api.return_value.do_auth.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG_INPUT | {"region": region[0], "brand": brand[0]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        "username": "test-username",
        "password": "test-password",
        "region": region[0],
        "brand": brand[0],
    }
    assert len(mock_whirlpool_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_auth_api", "mock_appliances_manager_api")
async def test_form_already_configured(hass: HomeAssistant, region, brand) -> None:
    """Test we handle cannot connect error."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {"region": region[0], "brand": brand[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG_INPUT
        | {
            "region": region[0],
            "brand": brand[0],
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_auth_api")
async def test_no_appliances_flow(
    hass: HomeAssistant, region, brand, mock_appliances_manager_api: MagicMock
) -> None:
    """Test we get an error with no appliances."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    mock_appliances_manager_api.return_value.aircons = []
    mock_appliances_manager_api.return_value.washer_dryers = []
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG_INPUT | {"region": region[0], "brand": brand[0]},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "no_appliances"}


@pytest.mark.usefixtures(
    "mock_auth_api", "mock_appliances_manager_api", "mock_whirlpool_setup_entry"
)
async def test_reauth_flow(hass: HomeAssistant, region, brand) -> None:
    """Test a successful reauth flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {"region": region[0], "brand": brand[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password", CONF_BRAND: brand[0]},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "new-password",
        "region": region[0],
        "brand": brand[0],
    }


@pytest.mark.usefixtures("mock_appliances_manager_api", "mock_whirlpool_setup_entry")
async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, region, brand, mock_auth_api: MagicMock
) -> None:
    """Test an authorization error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {"region": region[0], "brand": brand[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_auth_api.return_value.is_access_token_valid.return_value = False
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password", CONF_BRAND: brand[0]},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.usefixtures("mock_appliances_manager_api", "mock_whirlpool_setup_entry")
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (AccountLockedError, "account_locked"),
        (aiohttp.ClientConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_auth_error(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
    region,
    brand,
    mock_auth_api: MagicMock,
) -> None:
    """Test a connection error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {"region": region[0], "brand": brand[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_auth_api.return_value.do_auth.side_effect = exception
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password", CONF_BRAND: brand[0]},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}
