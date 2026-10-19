"""Test the Renault config flow."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import aiohttp
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_fixture,
    get_schema_suggested_value,
)
from renault_api.gigya.exceptions import (
    GigyaException,
    InvalidCredentialsException,
    InvalidVerificationCodeException,
    PendingTwoFactorAuthenticationException,
)
from renault_api.gigya.models import GigyaTfaEmail
from renault_api.kamereon import schemas
from renault_api.renault_account import RenaultAccount
from renault_api.renault_session import RenaultSession

from homeassistant import config_entries
from homeassistant.components.renault.const import DOMAIN, RenaultConfigurationKeys
from homeassistant.const import CONF_CODE, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import aiohttp_client

from .const import MOCK_ACCOUNT_ID, MOCK_CONFIG, MOCK_DEVICE_IDS, MOCK_LOGIN_TOKEN

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def _mock_login(session: RenaultSession, login_id: str, password: str) -> None:
    """Restore a login token like a successful Gigya login would."""
    session.set_login_token(MOCK_LOGIN_TOKEN)


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (Exception(), "unknown"),
        (aiohttp.ClientConnectionError(), "cannot_connect"),
        (
            InvalidCredentialsException(403042, "invalid loginID or password"),
            "invalid_credentials",
        ),
    ],
)
async def test_config_flow_single_account(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Raise error
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                RenaultConfigurationKeys.LOCALE: "fr_FR",
                RenaultConfigurationKeys.USERNAME: "email@test.com",
                RenaultConfigurationKeys.PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    data_schema = result["data_schema"].schema
    assert (
        get_schema_suggested_value(data_schema, RenaultConfigurationKeys.LOCALE)
        == "fr_FR"
    )
    assert (
        get_schema_suggested_value(data_schema, RenaultConfigurationKeys.USERNAME)
        == "email@test.com"
    )
    assert (
        get_schema_suggested_value(data_schema, RenaultConfigurationKeys.PASSWORD)
        == "test"
    )

    renault_account = AsyncMock()
    type(renault_account).account_id = PropertyMock(return_value="account_id_1")
    renault_account.get_vehicles.return_value = (
        schemas.KamereonVehiclesResponseSchema.loads(
            await async_load_fixture(hass, "vehicle_zoe_40.json", DOMAIN)
        )
    )

    # Account list single
    with (
        patch(
            "renault_api.renault_session.RenaultSession.login",
            autospec=True,
            side_effect=_mock_login,
        ),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                RenaultConfigurationKeys.LOCALE: "fr_FR",
                RenaultConfigurationKeys.USERNAME: "email@test.com",
                RenaultConfigurationKeys.PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "account_id_1"
    assert result["data"][RenaultConfigurationKeys.USERNAME] == "email@test.com"
    assert result["data"][RenaultConfigurationKeys.PASSWORD] == "test"
    assert result["data"][RenaultConfigurationKeys.LOGIN_TOKEN] == MOCK_LOGIN_TOKEN
    assert (
        result["data"][RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID] == "account_id_1"
    )
    assert result["data"][RenaultConfigurationKeys.LOCALE] == "fr_FR"
    assert result["context"]["unique_id"] == "account_id_1"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_no_account(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Account list empty
    with (
        patch(
            "renault_api.renault_session.RenaultSession.login",
            autospec=True,
            side_effect=_mock_login,
        ),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                RenaultConfigurationKeys.LOCALE: "fr_FR",
                RenaultConfigurationKeys.USERNAME: "email@test.com",
                RenaultConfigurationKeys.PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "kamereon_no_account"

    assert len(mock_setup_entry.mock_calls) == 0


async def test_config_flow_missing_vehicle_details(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test vehicle details missing from the vehicle list are requested separately."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    renault_vehicles = schemas.KamereonVehiclesResponseSchema.loads(
        await async_load_fixture(hass, "vehicle_zoe_40.json", DOMAIN)
    )
    renault_vehicles.vehicleLinks = renault_vehicles.vehicleLinks[:1]
    vehicle_details = renault_vehicles.vehicleLinks[0].vehicleDetails
    renault_vehicles.vehicleLinks[0].vehicleDetails = None
    renault_account = AsyncMock()
    type(renault_account).account_id = PropertyMock(return_value="account_id_1")
    renault_account.get_vehicles.return_value = renault_vehicles
    renault_account.get_api_vehicle.return_value.get_details.return_value = (
        vehicle_details
    )

    with (
        patch(
            "renault_api.renault_session.RenaultSession.login",
            autospec=True,
            side_effect=_mock_login,
        ),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                RenaultConfigurationKeys.LOCALE: "fr_FR",
                RenaultConfigurationKeys.USERNAME: "email@test.com",
                RenaultConfigurationKeys.PASSWORD: "test",
            },
        )

    renault_account.get_api_vehicle.assert_awaited_once_with("VF1ZOE40VIN")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "account_id_1"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_multiple_accounts(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test what happens if multiple Kamereon accounts are available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    renault_account_1 = RenaultAccount(
        "account_id_1",
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    renault_account_2 = RenaultAccount(
        "account_id_2",
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    renault_vehicles = schemas.KamereonVehiclesResponseSchema.loads(
        await async_load_fixture(hass, "renault/vehicle_zoe_40.json")
    )

    # Multiple accounts
    with (
        patch(
            "renault_api.renault_session.RenaultSession.login",
            autospec=True,
            side_effect=_mock_login,
        ),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account_1, renault_account_2],
        ),
        patch(
            "renault_api.renault_account.RenaultAccount.get_vehicles",
            return_value=renault_vehicles,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                RenaultConfigurationKeys.LOCALE: "fr_FR",
                RenaultConfigurationKeys.USERNAME: "email@test.com",
                RenaultConfigurationKeys.PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "kamereon"

    # Account selected
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID: "account_id_2"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "account_id_2"
    assert result["data"][RenaultConfigurationKeys.USERNAME] == "email@test.com"
    assert result["data"][RenaultConfigurationKeys.PASSWORD] == "test"
    assert result["data"][RenaultConfigurationKeys.LOGIN_TOKEN] == MOCK_LOGIN_TOKEN
    assert (
        result["data"][RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID] == "account_id_2"
    )
    assert result["data"][RenaultConfigurationKeys.LOCALE] == "fr_FR"
    assert result["context"]["unique_id"] == "account_id_2"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("config_entry")
async def test_config_flow_duplicate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test abort if unique_id configured."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    renault_account = RenaultAccount(
        "account_id_1",
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    renault_vehicles = schemas.KamereonVehiclesResponseSchema.loads(
        await async_load_fixture(hass, "renault/vehicle_zoe_50.json")
    )
    with (
        patch(
            "renault_api.renault_session.RenaultSession.login",
            autospec=True,
            side_effect=_mock_login,
        ),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account],
        ),
        patch(
            "renault_api.renault_account.RenaultAccount.get_vehicles",
            return_value=renault_vehicles,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                RenaultConfigurationKeys.LOCALE: "fr_FR",
                RenaultConfigurationKeys.USERNAME: "email@test.com",
                RenaultConfigurationKeys.PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0


async def test_reauth(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the start of the config flow."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {
        "name": "Mock Title",
        RenaultConfigurationKeys.USERNAME: "email@test.com",
    }
    assert result["errors"] == {}

    # Failed credentials
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=InvalidCredentialsException(403042, "invalid loginID or password"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={RenaultConfigurationKeys.PASSWORD: "any"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["description_placeholders"] == {
        "name": "Mock Title",
        RenaultConfigurationKeys.USERNAME: "email@test.com",
    }
    assert result2["errors"] == {"base": "invalid_credentials"}

    # Valid credentials
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        autospec=True,
        side_effect=_mock_login,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={RenaultConfigurationKeys.PASSWORD: "any"},
        )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"

    assert config_entry.data[RenaultConfigurationKeys.USERNAME] == "email@test.com"
    assert config_entry.data[RenaultConfigurationKeys.PASSWORD] == "any"
    assert config_entry.data[RenaultConfigurationKeys.LOGIN_TOKEN] == MOCK_LOGIN_TOKEN


async def test_reconfigure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure works."""
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    data_schema = result["data_schema"].schema
    assert (
        get_schema_suggested_value(data_schema, RenaultConfigurationKeys.LOCALE)
        == "fr_FR"
    )
    assert (
        get_schema_suggested_value(data_schema, RenaultConfigurationKeys.USERNAME)
        == "email@test.com"
    )
    assert (
        get_schema_suggested_value(data_schema, RenaultConfigurationKeys.PASSWORD)
        == "test"
    )

    renault_account = AsyncMock()
    type(renault_account).account_id = PropertyMock(return_value="account_id_1")
    renault_account.get_vehicles.return_value = (
        schemas.KamereonVehiclesResponseSchema.loads(
            await async_load_fixture(hass, "vehicle_zoe_40.json", DOMAIN)
        )
    )

    # Account list single
    with (
        patch(
            "renault_api.renault_session.RenaultSession.login",
            autospec=True,
            side_effect=_mock_login,
        ),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                RenaultConfigurationKeys.LOCALE: "fr_FR",
                RenaultConfigurationKeys.USERNAME: "email2@test.com",
                RenaultConfigurationKeys.PASSWORD: "test2",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert config_entry.data[RenaultConfigurationKeys.USERNAME] == "email2@test.com"
    assert config_entry.data[RenaultConfigurationKeys.PASSWORD] == "test2"
    assert config_entry.data[RenaultConfigurationKeys.LOGIN_TOKEN] == MOCK_LOGIN_TOKEN
    assert (
        config_entry.data[RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID]
        == "account_id_1"
    )
    assert config_entry.data[RenaultConfigurationKeys.LOCALE] == "fr_FR"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_mismatch(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure fails on account ID mismatch."""
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    data_schema = result["data_schema"].schema
    assert (
        get_schema_suggested_value(data_schema, RenaultConfigurationKeys.LOCALE)
        == "fr_FR"
    )
    assert (
        get_schema_suggested_value(data_schema, RenaultConfigurationKeys.USERNAME)
        == "email@test.com"
    )
    assert (
        get_schema_suggested_value(data_schema, RenaultConfigurationKeys.PASSWORD)
        == "test"
    )

    renault_account = AsyncMock()
    type(renault_account).account_id = PropertyMock(return_value="account_id_other")
    renault_account.get_vehicles.return_value = (
        schemas.KamereonVehiclesResponseSchema.loads(
            await async_load_fixture(hass, "vehicle_zoe_40.json", DOMAIN)
        )
    )

    # Account list single
    with (
        patch(
            "renault_api.renault_session.RenaultSession.login",
            autospec=True,
            side_effect=_mock_login,
        ),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                RenaultConfigurationKeys.LOCALE: "fr_FR",
                RenaultConfigurationKeys.USERNAME: "email2@test.com",
                RenaultConfigurationKeys.PASSWORD: "test2",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"

    # Unchanged values
    assert config_entry.data[RenaultConfigurationKeys.USERNAME] == "email@test.com"
    assert config_entry.data[RenaultConfigurationKeys.PASSWORD] == "test"
    assert config_entry.data[RenaultConfigurationKeys.LOGIN_TOKEN] == MOCK_LOGIN_TOKEN
    assert (
        config_entry.data[RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID]
        == "account_id_1"
    )
    assert config_entry.data[RenaultConfigurationKeys.LOCALE] == "fr_FR"

    assert len(mock_setup_entry.mock_calls) == 0


def _mock_complete_two_factor_auth(session: RenaultSession, code: str) -> None:
    """Log in and remember the device like a successful 2FA would."""
    session.set_login_token(MOCK_LOGIN_TOKEN)
    session.set_device_ids(MOCK_DEVICE_IDS)


def _mock_pending_login(session: RenaultSession, login_id: str, password: str) -> None:
    """Fail the login like an account requiring two-factor authentication."""
    raise PendingTwoFactorAuthenticationException(
        403101, "Pending Two-Factor Authentication", "reg-token"
    )


@pytest.fixture
def mock_pending_login() -> Generator[AsyncMock]:
    """Mock a login that requires two-factor authentication."""
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        autospec=True,
        side_effect=_mock_pending_login,
    ) as mock_login:
        yield mock_login


@pytest.fixture
def mock_two_factor_auth(
    mock_pending_login: AsyncMock, two_factor_emails: list[GigyaTfaEmail]
) -> Generator[AsyncMock]:
    """Mock the two-factor authentication calls."""
    with (
        patch(
            "renault_api.renault_session.RenaultSession.get_two_factor_auth_emails",
            return_value=two_factor_emails,
        ),
        patch(
            "renault_api.renault_session.RenaultSession.request_two_factor_auth_code",
        ) as mock_request_code,
        patch(
            "renault_api.renault_session.RenaultSession.complete_two_factor_auth",
            autospec=True,
            side_effect=_mock_complete_two_factor_auth,
        ),
    ):
        yield mock_request_code


@pytest.fixture
def two_factor_emails() -> list[GigyaTfaEmail]:
    """Email addresses registered for two-factor authentication."""
    return [GigyaTfaEmail(raw_data={}, id="email_id_1", obfuscated="e***@test.com")]


@pytest.fixture
async def mock_get_api_accounts(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Mock a single Kamereon account with a vehicle."""
    renault_account = RenaultAccount(
        "account_id_1",
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    with (
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account],
        ),
        patch(
            "renault_api.renault_account.RenaultAccount.get_vehicles",
            return_value=schemas.KamereonVehiclesResponseSchema.loads(
                await async_load_fixture(hass, "vehicle_zoe_40.json", DOMAIN)
            ),
        ),
    ):
        yield


@pytest.mark.usefixtures("mock_get_api_accounts")
async def test_config_flow_two_factor_auth(
    hass: HomeAssistant, mock_two_factor_auth: AsyncMock
) -> None:
    """Test the config flow with two-factor authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            RenaultConfigurationKeys.LOCALE: "fr_FR",
            RenaultConfigurationKeys.USERNAME: "email@test.com",
            RenaultConfigurationKeys.PASSWORD: "test",
        },
    )

    # A single email address is used without asking.
    mock_two_factor_auth.assert_awaited_once_with("email_id_1")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "two_factor_code"
    assert result["description_placeholders"] == {CONF_EMAIL: "e***@test.com"}
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "account_id_1"
    assert result["result"].unique_id == "account_id_1"
    assert result["data"][RenaultConfigurationKeys.PASSWORD] == "test"
    assert result["data"][RenaultConfigurationKeys.LOGIN_TOKEN] == MOCK_LOGIN_TOKEN
    assert result["data"][RenaultConfigurationKeys.DEVICE_IDS] == MOCK_DEVICE_IDS


@pytest.mark.usefixtures("mock_get_api_accounts")
@pytest.mark.parametrize(
    "two_factor_emails",
    [
        [
            GigyaTfaEmail(raw_data={}, id="email_id_1", obfuscated="e***@test.com"),
            GigyaTfaEmail(raw_data={}, id="email_id_2", obfuscated="o***@test.com"),
        ]
    ],
)
async def test_config_flow_two_factor_auth_multiple_emails(
    hass: HomeAssistant, mock_two_factor_auth: AsyncMock
) -> None:
    """Test the user selects the email address for two-factor authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            RenaultConfigurationKeys.LOCALE: "fr_FR",
            RenaultConfigurationKeys.USERNAME: "email@test.com",
            RenaultConfigurationKeys.PASSWORD: "test",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "two_factor_email"
    mock_two_factor_auth.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_EMAIL: "email_id_2"}
    )

    mock_two_factor_auth.assert_awaited_once_with("email_id_2")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "two_factor_code"
    assert result["description_placeholders"] == {CONF_EMAIL: "o***@test.com"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "account_id_1"
    assert result["data"][RenaultConfigurationKeys.DEVICE_IDS] == MOCK_DEVICE_IDS


@pytest.mark.usefixtures("mock_get_api_accounts", "mock_two_factor_auth")
async def test_config_flow_two_factor_invalid_code(hass: HomeAssistant) -> None:
    """Test a wrong two-factor authentication code can be corrected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            RenaultConfigurationKeys.LOCALE: "fr_FR",
            RenaultConfigurationKeys.USERNAME: "email@test.com",
            RenaultConfigurationKeys.PASSWORD: "test",
        },
    )

    with patch(
        "renault_api.renault_session.RenaultSession.complete_two_factor_auth",
        side_effect=InvalidVerificationCodeException(400006, "Wrong verification code"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_CODE: "000000"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "two_factor_code"
    assert result["errors"] == {"base": "invalid_code"}

    # The pending login stays valid after a wrong code.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "account_id_1"
    assert result["data"][RenaultConfigurationKeys.LOGIN_TOKEN] == MOCK_LOGIN_TOKEN


@pytest.mark.usefixtures("mock_get_api_accounts", "mock_two_factor_auth")
@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (aiohttp.ClientConnectionError(), "cannot_connect"),
        (aiohttp.ClientResponseError(Mock(), (), status=500), "cannot_connect"),
        (GigyaException(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_config_flow_two_factor_code_abort(
    hass: HomeAssistant, exception: Exception, reason: str
) -> None:
    """Test the flow aborts on errors other than a wrong code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            RenaultConfigurationKeys.LOCALE: "fr_FR",
            RenaultConfigurationKeys.USERNAME: "email@test.com",
            RenaultConfigurationKeys.PASSWORD: "test",
        },
    )

    with patch(
        "renault_api.renault_session.RenaultSession.complete_two_factor_auth",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_CODE: "123456"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("target", "kwargs", "reason"),
    [
        pytest.param(
            "get_two_factor_auth_emails",
            {"side_effect": aiohttp.ClientConnectionError()},
            "cannot_connect",
            id="get_emails_connection_error",
        ),
        pytest.param(
            "get_two_factor_auth_emails",
            {"return_value": []},
            "two_factor_no_email",
            id="no_email",
        ),
        pytest.param(
            "request_two_factor_auth_code",
            {"side_effect": GigyaException()},
            "cannot_connect",
            id="request_code_error",
        ),
        pytest.param(
            "request_two_factor_auth_code",
            {"side_effect": aiohttp.ClientResponseError(Mock(), (), status=500)},
            "cannot_connect",
            id="request_code_http_error",
        ),
        pytest.param(
            "get_two_factor_auth_emails",
            {"side_effect": Exception()},
            "unknown",
            id="get_emails_unexpected_error",
        ),
        pytest.param(
            "request_two_factor_auth_code",
            {"side_effect": Exception()},
            "unknown",
            id="request_code_unexpected_error",
        ),
    ],
)
@pytest.mark.usefixtures("mock_two_factor_auth")
async def test_config_flow_two_factor_auth_abort(
    hass: HomeAssistant, target: str, kwargs: dict[str, Any], reason: str
) -> None:
    """Test the flow aborts when the two-factor authentication code can't be sent."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(f"renault_api.renault_session.RenaultSession.{target}", **kwargs):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                RenaultConfigurationKeys.LOCALE: "fr_FR",
                RenaultConfigurationKeys.USERNAME: "email@test.com",
                RenaultConfigurationKeys.PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (aiohttp.ClientConnectionError(), "cannot_connect"),
        (GigyaException(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_reauth_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test errors during reauth."""
    result = await config_entry.start_reauth_flow(hass)

    with patch(
        "renault_api.renault_session.RenaultSession.login", side_effect=exception
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={RenaultConfigurationKeys.PASSWORD: "any"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    with patch(
        "renault_api.renault_session.RenaultSession.login",
        autospec=True,
        side_effect=_mock_login,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={RenaultConfigurationKeys.PASSWORD: "any"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_two_factor_auth")
async def test_reauth_two_factor_auth(
    hass: HomeAssistant, mock_pending_login: AsyncMock
) -> None:
    """Test reauth with two-factor authentication restores the device ids first."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **MOCK_CONFIG,
            RenaultConfigurationKeys.DEVICE_IDS: {
                "gmid": "old-gmid",
                "ucid": "old-ucid",
            },
        },
        unique_id=MOCK_ACCOUNT_ID,
    )
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    device_ids: list[dict[str, str]] = []

    def _record_device_ids(
        session: RenaultSession, login_id: str, password: str
    ) -> None:
        device_ids.append(session.device_ids)
        _mock_pending_login(session, login_id, password)

    mock_pending_login.side_effect = _record_device_ids
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={RenaultConfigurationKeys.PASSWORD: "new-password"},
    )

    assert device_ids == [{"gmid": "old-gmid", "ucid": "old-ucid"}]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "two_factor_code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[RenaultConfigurationKeys.PASSWORD] == "new-password"
    assert config_entry.data[RenaultConfigurationKeys.LOGIN_TOKEN] == MOCK_LOGIN_TOKEN
    assert config_entry.data[RenaultConfigurationKeys.DEVICE_IDS] == MOCK_DEVICE_IDS


@pytest.mark.usefixtures("mock_get_api_accounts", "mock_two_factor_auth")
async def test_reconfigure_two_factor_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
    mock_pending_login: AsyncMock,
) -> None:
    """Test reconfigure with two-factor authentication restores the device ids first."""
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            RenaultConfigurationKeys.DEVICE_IDS: {
                "gmid": "old-gmid",
                "ucid": "old-ucid",
            },
        },
    )
    result = await config_entry.start_reconfigure_flow(hass)

    device_ids: list[dict[str, str]] = []

    def _record_device_ids(
        session: RenaultSession, login_id: str, password: str
    ) -> None:
        device_ids.append(session.device_ids)
        _mock_pending_login(session, login_id, password)

    mock_pending_login.side_effect = _record_device_ids
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            RenaultConfigurationKeys.LOCALE: "fr_FR",
            RenaultConfigurationKeys.USERNAME: "email2@test.com",
            RenaultConfigurationKeys.PASSWORD: "test2",
        },
    )

    assert device_ids == [{"gmid": "old-gmid", "ucid": "old-ucid"}]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "two_factor_code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[RenaultConfigurationKeys.USERNAME] == "email2@test.com"
    assert config_entry.data[RenaultConfigurationKeys.PASSWORD] == "test2"
    assert config_entry.data[RenaultConfigurationKeys.LOGIN_TOKEN] == MOCK_LOGIN_TOKEN
    assert config_entry.data[RenaultConfigurationKeys.DEVICE_IDS] == MOCK_DEVICE_IDS
    assert len(mock_setup_entry.mock_calls) == 1
