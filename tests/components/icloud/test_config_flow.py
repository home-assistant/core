"""Tests for the iCloud config flow."""

from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from pyicloud.const import AppleAuthError
from pyicloud.exceptions import (
    PyiCloud2FARequiredException,
    PyiCloudAcceptTermsException,
    PyiCloudAPIResponseException,
    PyiCloudAuthRequiredException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
    PyiCloudServiceUnavailable,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests import Response

from homeassistant.components.icloud.config_flow import (
    CONF_REQUEST_NEW_CODE,
    CONF_TRUSTED_DEVICE,
    CONF_VERIFICATION_CODE,
)
from homeassistant.components.icloud.const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_INCLUDE_COMPLETED,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_INCLUDE_COMPLETED,
    DEFAULT_MAX_INTERVAL,
    DEFAULT_WITH_FAMILY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    MOCK_CONFIG,
    PASSWORD,
    PASSWORD_2,
    TRUSTED_DEVICES,
    USERNAME,
    WITH_FAMILY,
)


@pytest.fixture(name="icloud_bypass_setup", autouse=True)
def icloud_bypass_setup_fixture():
    """Mock component setup."""
    with patch("homeassistant.components.icloud.async_setup_entry", return_value=None):
        yield


@pytest.fixture(name="service")
def mock_controller_service():
    """Mock a successful service."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=True)
        yield service_mock


@pytest.fixture(name="service_2fa")
def mock_controller_2fa_service():
    """Mock a successful 2fa service."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = True
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.validate_2fa_code = Mock(return_value=True)
        service_mock.return_value.is_trusted_session = False
        yield service_mock


@pytest.fixture(name="service_2fa_failed_request")
def mock_controller_2fa_failed_request_service():
    """Mock a request failure 2fa service."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = True
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.is_trusted_session = False
        yield service_mock


@pytest.fixture(name="service_authenticated")
def mock_controller_service_authenticated():
    """Mock a successful service while already authenticate."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = False
        service_mock.return_value.is_trusted_session = True
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_2fa_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=True)
        yield service_mock


@pytest.fixture(name="service_password_update")
def mock_controller_service_password_authenticated(service_authenticated: MagicMock):
    """Mock a service that needs a password update."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        return_value=service_authenticated(),
    ) as service_mock:
        yield service_mock


@pytest.fixture(name="service_password_update_failed")
def mock_controller_service_password_failed():
    """Mock a service that needs a password update but fails."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=[
            PyiCloudFailedLoginException(msg="Password updated"),
            PyiCloudFailedLoginException(msg="Password updated"),
        ],
    ) as service_mock:
        yield service_mock


@pytest.fixture(name="service_authenticated_no_device")
def mock_controller_service_authenticated_no_device():
    """Mock a successful service while already authenticate, but without device."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = False
        # Pinned: a bare mock attribute is never "unknown", so the challenge
        # test would pass whatever the delivery-route check did.
        service_mock.return_value.two_factor_delivery_method = "trusted_device"
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=True)
        service_mock.return_value.devices = {}
        yield service_mock


@pytest.fixture(name="service_authenticated_not_trusted")
def mock_controller_service_authenticated_not_trusted():
    """Mock a successful service already authenticated but not trusted."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = False
        service_mock.return_value.is_trusted_session = False
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_2fa_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=True)
        yield service_mock


@pytest.fixture(name="service_send_verification_code_failed")
def mock_controller_service_send_verification_code_failed():
    """Mock a failed service during sending verification code step."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=False)
        yield service_mock


@pytest.fixture(name="service_validate_2fa_code_failed")
def mock_controller_service_validate_2fa_code_failed():
    """Mock a failed service during validation of 2FA verification code step."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = True
        service_mock.return_value.validate_2fa_code = Mock(return_value=False)
        yield service_mock


@pytest.fixture(name="service_validate_verification_code_failed")
def mock_controller_service_validate_verification_code_failed():
    """Mock a failed service during validation of verification code step."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=False)
        yield service_mock


def _accept_2fa_code(service: MagicMock) -> None:
    """Accept the next 2FA code, which makes the session trusted."""

    def _validate_2fa_code(code: str) -> bool:
        service.requires_2fa = False
        service.requires_2sa = False
        return True

    service.validate_2fa_code = Mock(side_effect=_validate_2fa_code)


@pytest.mark.usefixtures("service")
async def test_user(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # test with required
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE


@pytest.mark.usefixtures("service_authenticated")
async def test_user_with_cookie(hass: HomeAssistant) -> None:
    """Test user config with presence of a cookie."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # test with all provided
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_WITH_FAMILY: WITH_FAMILY,
            CONF_INCLUDE_COMPLETED: True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_WITH_FAMILY] == WITH_FAMILY
    assert result["data"][CONF_MAX_INTERVAL] == DEFAULT_MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == DEFAULT_GPS_ACCURACY_THRESHOLD
    assert result["data"][CONF_INCLUDE_COMPLETED] is True


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test that the include_completed option can be toggled."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch("homeassistant.components.icloud.async_setup_entry", return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_INCLUDE_COMPLETED: True}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_INCLUDE_COMPLETED] is True
    assert config_entry.options[CONF_INCLUDE_COMPLETED] is True


@pytest.mark.usefixtures("service_authenticated")
async def test_user_defaults(hass: HomeAssistant) -> None:
    """Test that the defaults are stored when the user does not override them."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert result["data"][CONF_INCLUDE_COMPLETED] == DEFAULT_INCLUDE_COMPLETED


@pytest.mark.usefixtures("service_authenticated")
async def test_login_failed(hass: HomeAssistant) -> None:
    """Test when we have errors during login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=PyiCloudFailedLoginException(msg="Invalid login"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("service_authenticated")
async def test_connection_error(hass: HomeAssistant) -> None:
    """Test when iCloud is unreachable during login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=PyiCloudConnectionException(reason="Connection error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_accept_terms_during_login(hass: HomeAssistant) -> None:
    """Test that a login blocked by updated terms asks the user to accept."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=[
            PyiCloudAcceptTermsException("Terms not accepted"),
            MagicMock(requires_2fa=False, requires_2sa=False),
        ],
    ) as service_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "accept_terms"
        assert result["errors"] == {}
        assert service_mock.call_args.kwargs["accept_terms"] is False

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert service_mock.call_args.kwargs["accept_terms"] is True


async def test_accept_terms_failure_is_reported(hass: HomeAssistant) -> None:
    """Test that a terms acceptance which does not stick is reported."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=PyiCloudAcceptTermsException("Terms not accepted"),
    ) as service_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "accept_terms"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "accept_terms"
        assert result["errors"] == {"base": "accept_terms_failed"}

        # Accepting a second time gets past Apple and the flow completes.
        service_mock.side_effect = None
        service_mock.return_value = MagicMock(requires_2fa=False, requires_2sa=False)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_disables_pyicloud_monitor(
    hass: HomeAssistant, service_authenticated: MagicMock
) -> None:
    """Test the config flow disables pyicloud's own Find My monitor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert service_authenticated.call_args.kwargs["refresh_interval"] is None


@pytest.mark.usefixtures("service_authenticated_no_device")
async def test_no_device(hass: HomeAssistant) -> None:
    """Test when we have no devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_device"


@contextmanager
def _service_rejecting_the_device_fetch(
    error: Exception, delivery: str = "trusted_device"
):
    """Mock a service that authenticates but is turned down reading devices."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = False
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=True)
        # Pinned: a bare mock attribute is never "unknown", so the challenge
        # test would pass whatever the delivery-route check did.
        service_mock.return_value.two_factor_delivery_method = delivery
        type(service_mock.return_value).devices = PropertyMock(side_effect=error)
        yield service_mock


async def _submit_user_form(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the user flow and submit the login form, as a user does."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )


def _recover_device_fetch(service_mock: MagicMock) -> None:
    """Let the device fetch succeed, as it does once iCloud answers again."""
    type(service_mock.return_value).devices = PropertyMock(return_value=[MagicMock()])


async def test_device_fetch_challenged_asks_for_a_code(hass: HomeAssistant) -> None:
    """Test that a challenge while reading the devices asks for the code.

    iCloud turns down a session when it is refreshed to read the devices
    rather than while logging in, so the challenge arrives after the login
    the flow already treated as successful.
    """
    with _service_rejecting_the_device_fetch(
        PyiCloud2FARequiredException(USERNAME, Mock(spec=Response))
    ):
        result = await _submit_user_form(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "verification_code"


async def test_device_fetch_rejected_returns_to_the_form(hass: HomeAssistant) -> None:
    """Test that a rejection while reading the devices is reported.

    The flow used to end on the unhandled exception, which left the user with
    an error they could not act on and no way back to the password.
    """
    with _service_rejecting_the_device_fetch(
        PyiCloudAPIResponseException(
            "Authentication required for Account.",
            AppleAuthError.LOGIN_TOKEN_EXPIRED,
        )
    ) as service_mock:
        result = await _submit_user_form(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}

        _recover_device_fetch(service_mock)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("service")
async def test_trusted_device(hass: HomeAssistant) -> None:
    """Test trusted_device step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE


@pytest.mark.usefixtures("service")
async def test_trusted_device_success(hass: HomeAssistant) -> None:
    """Test trusted_device step success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRUSTED_DEVICE: 0}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE


async def test_send_verification_code_failed(
    hass: HomeAssistant, service_send_verification_code_failed: MagicMock
) -> None:
    """Test when we have errors during send_verification_code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRUSTED_DEVICE: 0}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {CONF_TRUSTED_DEVICE: "send_verification_code"}

    service = service_send_verification_code_failed.return_value
    service.send_verification_code.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRUSTED_DEVICE: 0}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE

    service.requires_2sa = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("service")
async def test_verification_code(hass: HomeAssistant) -> None:
    """Test verification_code step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRUSTED_DEVICE: 0}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE


async def test_verification_code_success(
    hass: HomeAssistant, service: MagicMock
) -> None:
    """Test verification_code step success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRUSTED_DEVICE: 0}
    )
    service.return_value.requires_2sa = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_WITH_FAMILY] == DEFAULT_WITH_FAMILY
    assert result["data"][CONF_MAX_INTERVAL] == DEFAULT_MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == DEFAULT_GPS_ACCURACY_THRESHOLD


async def test_validate_verification_code_failed(
    hass: HomeAssistant, service_validate_verification_code_failed: MagicMock
) -> None:
    """Test when we have errors during validate_verification_code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRUSTED_DEVICE: 0}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {"base": "validate_verification_code"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRUSTED_DEVICE: 0}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE

    service = service_validate_verification_code_failed.return_value
    service.validate_verification_code.return_value = True
    service.requires_2sa = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_2fa_code_success(hass: HomeAssistant, service_2fa: MagicMock) -> None:
    """Test 2fa step success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {}

    service_2fa.return_value.requires_2fa = False
    service_2fa.return_value.requires_2sa = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_WITH_FAMILY] == DEFAULT_WITH_FAMILY
    assert result["data"][CONF_MAX_INTERVAL] == DEFAULT_MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == DEFAULT_GPS_ACCURACY_THRESHOLD


async def test_2fa_new_code_success(
    hass: HomeAssistant, service_2fa: MagicMock
) -> None:
    """Test 2fa step success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {}

    service_2fa.return_value.requires_2fa = False
    service_2fa.return_value.requires_2sa = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REQUEST_NEW_CODE: True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {}


async def test_validate_2fa_code_failed(
    hass: HomeAssistant, service_validate_2fa_code_failed: MagicMock
) -> None:
    """Test when we have errors during validate_verification_code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {"base": "validate_verification_code"}

    _accept_2fa_code(service_validate_2fa_code_failed.return_value)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_validate_2fa_code_not_provided(
    hass: HomeAssistant, service_2fa: MagicMock
) -> None:
    """Test when we have errors during validate_verification_code if the user didn't provide a code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: ""}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {"base": "validate_verification_code"}

    _accept_2fa_code(service_2fa.return_value)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_2fa_code_failed_request(
    hass: HomeAssistant, service_2fa_failed_request: MagicMock
) -> None:
    """Test 2fa step failed request."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {}

    service_2fa_failed_request.return_value.request_2fa_code.side_effect = (
        PyiCloudAPIResponseException(reason="PyiCloud error")
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REQUEST_NEW_CODE: True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {"base": "send_verification_code"}

    service_2fa_failed_request.return_value.request_2fa_code.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REQUEST_NEW_CODE: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    _accept_2fa_code(service_2fa_failed_request.return_value)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_2fa_code_non_pyicloud_error(
    hass: HomeAssistant, service_2fa_failed_request: MagicMock
) -> None:
    """Test 2fa step failed request (non-PyiCloud error)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {}

    service_2fa_failed_request.return_value.request_2fa_code.side_effect = Exception(
        "Non-PyiCloud error"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REQUEST_NEW_CODE: True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {"base": "send_verification_code"}

    service_2fa_failed_request.return_value.request_2fa_code.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REQUEST_NEW_CODE: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    _accept_2fa_code(service_2fa_failed_request.return_value)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_2fa_code_returned_false(
    hass: HomeAssistant, service_2fa_failed_request: MagicMock
) -> None:
    """Test 2fa step failed API response (returned False)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {}

    service_2fa_failed_request.return_value.request_2fa_code.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REQUEST_NEW_CODE: True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {"base": "send_verification_code"}

    service_2fa_failed_request.return_value.request_2fa_code.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REQUEST_NEW_CODE: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    _accept_2fa_code(service_2fa_failed_request.return_value)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_accept_terms_during_verification(hass: HomeAssistant) -> None:
    """Test that terms demanded while entering a code can be accepted."""
    challenged = MagicMock(requires_2fa=True, requires_2sa=True)
    challenged.validate_2fa_code = Mock(
        side_effect=PyiCloudAcceptTermsException("Terms not accepted")
    )

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=[challenged, MagicMock(requires_2fa=False, requires_2sa=False)],
    ) as service_mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == CONF_VERIFICATION_CODE

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "accept_terms"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert service_mock.call_args.kwargs["accept_terms"] is True


async def test_terms_demanded_while_entering_a_flagged_code(
    hass: HomeAssistant,
) -> None:
    """Test that accepting terms does not send a clean login back to code entry.

    The challenge belongs to the session the terms demand discards. Leaving the
    flag set would route the login that follows it to the code form again,
    although nothing is asking for a code any more.
    """
    challenged = MagicMock(requires_2fa=False, requires_2sa=False)
    challenged.two_factor_delivery_method = "sms"
    type(challenged).devices = PropertyMock(
        side_effect=PyiCloud2FARequiredException(USERNAME, Mock(spec=Response))
    )
    challenged.validate_2fa_code = Mock(
        side_effect=PyiCloudAcceptTermsException("Terms not accepted")
    )
    clean = MagicMock(requires_2fa=False, requires_2sa=False)
    clean.devices = [MagicMock()]

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=[challenged, clean],
    ):
        result = await _submit_user_form(hass)
        assert result["step_id"] == CONF_VERIFICATION_CODE

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_VERIFICATION_CODE: "0"}
        )
        assert result["step_id"] == "accept_terms"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_terms_demanded_when_logging_in_again_without_the_session(
    hass: HomeAssistant,
) -> None:
    """Test that the login without the stored session can ask for the terms."""
    refused = MagicMock()
    refused.authenticate.side_effect = PyiCloudAcceptTermsException("Terms")
    accepted = MagicMock(requires_2fa=False, requires_2sa=False)
    accepted.devices = [MagicMock()]

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=[
            PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response)),
            refused,
            accepted,
        ],
    ):
        result = await _submit_user_form(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "accept_terms"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_consent_to_the_terms_is_kept_when_logging_in_again(
    hass: HomeAssistant,
) -> None:
    """Test that the login without the stored session carries the given consent.

    The terms are accepted, and the login that follows is then turned down for
    its stored session. The login that replaces it must not ask again.
    """
    retry_service = MagicMock(requires_2fa=False, requires_2sa=False)
    retry_service.devices = [MagicMock()]

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=[
            PyiCloudAcceptTermsException("Terms"),
            PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response)),
            retry_service,
        ],
    ) as service_mock:
        result = await _submit_user_form(hass)
        assert result["step_id"] == "accept_terms"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert service_mock.call_args_list[2].kwargs["accept_terms"] is True


@pytest.mark.usefixtures("service_password_update")
async def test_password_update(hass: HomeAssistant) -> None:
    """Test that password reauthentication works successfully."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)
    config_entry.runtime_data = MagicMock(api=None)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: PASSWORD_2}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == PASSWORD_2


async def test_password_update_wrong_password(
    hass: HomeAssistant, service_password_update_failed: MagicMock
) -> None:
    """Test password reauthentication with wrong password returns error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
        unique_id=USERNAME,
    )
    config_entry.add_to_hass(hass)
    config_entry.runtime_data = MagicMock(api=None)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: PASSWORD_2}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}

    service_password_update_failed.side_effect = None
    service_password_update_failed.return_value.requires_2fa = False
    service_password_update_failed.return_value.requires_2sa = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: PASSWORD_2}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_accept_terms_during_reauth(hass: HomeAssistant) -> None:
    """Test that reauthentication blocked by updated terms can accept them."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)
    config_entry.runtime_data = MagicMock(api=None)

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=[
            PyiCloudAcceptTermsException("Terms not accepted"),
            MagicMock(requires_2fa=False, requires_2sa=False),
        ],
    ) as service_mock:
        result = await config_entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: PASSWORD_2}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "accept_terms"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert service_mock.call_args.kwargs["accept_terms"] is True

    assert config_entry.data[CONF_PASSWORD] == PASSWORD_2


@pytest.mark.usefixtures("service")
async def test_create_icloud_storage_dir(hass: HomeAssistant) -> None:
    """Test that the iCloud storage directory is created if it does not exist."""
    with (
        patch(
            "homeassistant.components.icloud.config_flow.os.path.exists",
            return_value=False,
        ) as mocked_path,
        patch(
            "homeassistant.components.icloud.config_flow.os.makedirs"
        ) as makedirs_mock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        mocked_path.return_value = True

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == CONF_TRUSTED_DEVICE
        makedirs_mock.assert_called_once()


async def test_device_fetch_during_an_outage_keeps_the_session(
    hass: HomeAssistant,
) -> None:
    """Test that iCloud being unavailable is reported without losing the session.

    PyiCloudServiceUnavailable derives straight from PyiCloudException, so it
    misses the handled set and used to escape as an unhandled flow error. It
    is iCloud failing rather than refusing: the stored session is not at fault
    and carries the trust token, so it has to survive the outage.
    """
    with _service_rejecting_the_device_fetch(
        PyiCloudServiceUnavailable("iCloud is unavailable")
    ) as service_mock:
        result = await _submit_user_form(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
        service_mock.return_value.session.clear_persistence.assert_not_called()

        _recover_device_fetch(service_mock)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_device_fetch_challenge_with_no_route_asks_for_the_password(
    hass: HomeAssistant,
) -> None:
    """Test that a challenge from the fetch with no route goes to the password.

    The same dead end the login path avoids: iCloud reports the challenge but
    nothing can send a code for it, so the code entry form cannot be
    completed. A fresh login raises the challenge again with a route behind
    it.
    """
    with _service_rejecting_the_device_fetch(
        PyiCloud2FARequiredException(USERNAME, Mock(spec=Response)),
        delivery="unknown",
    ) as service_mock:
        result = await _submit_user_form(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "send_verification_code"}

        _recover_device_fetch(service_mock)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_device_fetch_unreachable_keeps_the_session(
    hass: HomeAssistant,
) -> None:
    """Test that being unable to reach iCloud reading the devices is reported as such.

    It says nothing about the credentials or the session, which has to
    survive for the trust token it carries.
    """
    with _service_rejecting_the_device_fetch(
        PyiCloudConnectionException(reason="Connection error")
    ) as service_mock:
        result = await _submit_user_form(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

        _recover_device_fetch(service_mock)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    service_mock.assert_called_once()


async def test_retry_login_unreachable_is_a_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test that iCloud being unreachable on the second login is reported as such.

    The stored session is rejected, so the flow logs in again without it; the
    outage is then not a reason to blame the password or report an unknown
    error.
    """
    retry_service = MagicMock()
    retry_service.authenticate.side_effect = PyiCloudConnectionException(
        reason="Connection error"
    )
    recovered_service = MagicMock(requires_2fa=False, requires_2sa=False)
    recovered_service.devices = [MagicMock()]
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=[
            PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response)),
            retry_service,
            recovered_service,
        ],
    ):
        result = await _submit_user_form(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_changed_credentials_after_an_outage_are_logged_in_again(
    hass: HomeAssistant,
) -> None:
    """Test that the login kept through an outage is not reused for new credentials.

    The session survives an outage because it carries the trust token, but it
    belongs to the account that was entered. If the user corrects the Apple ID
    or the password on the same form, those have to be validated rather than
    the old login being trusted for them.
    """
    with _service_rejecting_the_device_fetch(
        PyiCloudServiceUnavailable("iCloud is unavailable")
    ) as service_mock:
        result = await _submit_user_form(hass)
        assert result["errors"] == {"base": "unknown"}

        _recover_device_fetch(service_mock)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "other@me.com", CONF_PASSWORD: "other"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "other@me.com"
    assert result["result"].unique_id == "other@me.com"
    assert service_mock.call_count == 2
    assert service_mock.call_args.args[:2] == ("other@me.com", "other")


async def test_switching_to_a_configured_account_after_an_outage_is_refused(
    hass: HomeAssistant,
) -> None:
    """Test that the account submitted last is the one checked for duplicates."""
    MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_USERNAME: "other@me.com"},
        unique_id="other@me.com",
    ).add_to_hass(hass)

    with _service_rejecting_the_device_fetch(
        PyiCloudServiceUnavailable("iCloud is unavailable")
    ) as service_mock:
        result = await _submit_user_form(hass)
        assert result["type"] is FlowResultType.FORM

        _recover_device_fetch(service_mock)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "other@me.com", CONF_PASSWORD: "other"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
