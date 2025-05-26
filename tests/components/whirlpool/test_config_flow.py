"""Test the Whirlpool Sixth Sense config flow."""

from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from whirlpool.auth import AccountLockedError
from whirlpool.backendselector import Brand, Region

from homeassistant import config_entries
from homeassistant.components.whirlpool.const import CONF_BRAND, DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG_INPUT = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


def assert_successful_user_flow(
    mock_whirlpool_setup_entry: MagicMock,
    result: ConfigFlowResult,
    region: str,
    brand: str,
) -> None:
    """Assert that the flow was successful."""
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_USERNAME: CONFIG_INPUT[CONF_USERNAME],
        CONF_PASSWORD: CONFIG_INPUT[CONF_PASSWORD],
        CONF_REGION: region,
        CONF_BRAND: brand,
    }
    assert result["result"].unique_id == CONFIG_INPUT[CONF_USERNAME]
    assert len(mock_whirlpool_setup_entry.mock_calls) == 1


def assert_successful_reauth_flow(
    mock_entry: MockConfigEntry,
    result: ConfigFlowResult,
    region: str,
    brand: str,
) -> None:
    """Assert that the reauth flow was successful."""
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data == {
        CONF_USERNAME: CONFIG_INPUT[CONF_USERNAME],
        CONF_PASSWORD: "new-password",
        CONF_REGION: region[0],
        CONF_BRAND: brand[0],
    }


@pytest.fixture(name="mock_whirlpool_setup_entry")
def fixture_mock_whirlpool_setup_entry():
    """Set up async_setup_entry fixture."""
    with patch(
        "homeassistant.components.whirlpool.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.mark.usefixtures("mock_auth_api", "mock_appliances_manager_api")
async def test_user_flow(
    hass: HomeAssistant,
    region: tuple[str, Region],
    brand: tuple[str, Brand],
    mock_backend_selector_api: MagicMock,
    mock_whirlpool_setup_entry: MagicMock,
) -> None:
    """Test successful flow initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]}
    )

    assert_successful_user_flow(mock_whirlpool_setup_entry, result, region[0], brand[0])
    mock_backend_selector_api.assert_called_once_with(brand[1], region[1])


async def test_user_flow_invalid_auth(
    hass: HomeAssistant,
    region: tuple[str, Region],
    brand: tuple[str, Brand],
    mock_auth_api: MagicMock,
    mock_whirlpool_setup_entry: MagicMock,
) -> None:
    """Test invalid authentication in the flow initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_auth_api.return_value.is_access_token_valid.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Test that it succeeds if the authentication is valid
    mock_auth_api.return_value.is_access_token_valid.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]}
    )
    assert_successful_user_flow(mock_whirlpool_setup_entry, result, region[0], brand[0])


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
async def test_user_flow_auth_error(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
    region: tuple[str, Region],
    brand: tuple[str, Brand],
    mock_auth_api: MagicMock,
    mock_whirlpool_setup_entry: MagicMock,
) -> None:
    """Test authentication exceptions in the flow initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_auth_api.return_value.do_auth.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG_INPUT
        | {
            CONF_REGION: region[0],
            CONF_BRAND: brand[0],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Test that it succeeds after the error is cleared
    mock_auth_api.return_value.do_auth.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]}
    )

    assert_successful_user_flow(mock_whirlpool_setup_entry, result, region[0], brand[0])


@pytest.mark.usefixtures("mock_auth_api", "mock_appliances_manager_api")
async def test_already_configured(
    hass: HomeAssistant, region: tuple[str, Region], brand: tuple[str, Brand]
) -> None:
    """Test that configuring the integration twice with the same data fails."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_auth_api")
async def test_no_appliances_flow(
    hass: HomeAssistant,
    region: tuple[str, Region],
    brand: tuple[str, Brand],
    mock_appliances_manager_api: MagicMock,
    mock_whirlpool_setup_entry: MagicMock,
) -> None:
    """Test we get an error with no appliances."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    original_aircons = mock_appliances_manager_api.return_value.aircons
    mock_appliances_manager_api.return_value.aircons = []
    mock_appliances_manager_api.return_value.washer_dryers = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_appliances"}

    # Test that it succeeds if appliances are found
    mock_appliances_manager_api.return_value.aircons = original_aircons
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]}
    )

    assert_successful_user_flow(mock_whirlpool_setup_entry, result, region[0], brand[0])


@pytest.mark.usefixtures(
    "mock_auth_api", "mock_appliances_manager_api", "mock_whirlpool_setup_entry"
)
async def test_reauth_flow(
    hass: HomeAssistant, region: tuple[str, Region], brand: tuple[str, Brand]
) -> None:
    """Test a successful reauth flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password", CONF_BRAND: brand[0]}
    )

    assert_successful_reauth_flow(mock_entry, result, region, brand)


@pytest.mark.usefixtures("mock_appliances_manager_api", "mock_whirlpool_setup_entry")
async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    region: tuple[str, Region],
    brand: tuple[str, Brand],
    mock_auth_api: MagicMock,
) -> None:
    """Test an authorization error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_auth_api.return_value.is_access_token_valid.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password", CONF_BRAND: brand[0]},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Test that it succeeds if the credentials are valid
    mock_auth_api.return_value.is_access_token_valid.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password", CONF_BRAND: brand[0]}
    )

    assert_successful_reauth_flow(mock_entry, result, region, brand)


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
    region: tuple[str, Region],
    brand: tuple[str, Brand],
    mock_auth_api: MagicMock,
) -> None:
    """Test a connection error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {CONF_REGION: region[0], CONF_BRAND: brand[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_auth_api.return_value.do_auth.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password", CONF_BRAND: brand[0]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Test that it succeeds if the exception is cleared
    mock_auth_api.return_value.do_auth.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password", CONF_BRAND: brand[0]}
    )

    assert_successful_reauth_flow(mock_entry, result, region, brand)
