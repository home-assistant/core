"""Tests for the iCloud config flow."""

from unittest.mock import MagicMock, Mock, PropertyMock, patch

from pyicloud.const import AppleAuthError
from pyicloud.exceptions import (
    PyiCloud2FARequiredException,
    PyiCloudAPIResponseException,
    PyiCloudAuthRequiredException,
    PyiCloudFailedLoginException,
    PyiCloudServiceNotActivatedException,
)
import pytest
from requests import Response

from homeassistant.components.icloud.config_flow import (
    CONF_REQUEST_NEW_CODE,
    CONF_VERIFICATION_CODE,
)
from homeassistant.components.icloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import DEVICE, MOCK_CONFIG, USER_INFO, USERNAME

from tests.common import MockConfigEntry


class MockDevice(dict):
    """Device payload that answers status() with itself, as pyicloud does."""

    def status(self, fields):
        """Return every requested field, as AppleDevice.status does."""
        return self


class MockDevices(list):
    """Devices response that also carries the account's user info."""

    user_info = USER_INFO


@pytest.fixture(name="service_2fa")
def mock_controller_2fa_service():
    """Mock a successful 2fa service."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = True
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.validate_2fa_code = Mock(return_value=True)
        service_mock.return_value.is_trusted_session = False
        service_mock.return_value.two_factor_delivery_method = "trusted_device"
        yield service_mock


@pytest.fixture(name="service_2fa_failed")
def mock_controller_2fa_service_failed():
    """Mock a failed 2fa service."""
    with (
        patch(
            "homeassistant.components.icloud.account.PyiCloudService"
        ) as service_mock,
        patch(
            "homeassistant.components.icloud.config_flow.PyiCloudService", service_mock
        ),
    ):
        service_mock.side_effect = PyiCloudFailedLoginException("Invalid login")
        yield service_mock


@pytest.fixture(name="service_auth_required")
def mock_controller_auth_required_service():
    """Mock a service that reports the session needs authenticating again."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_mock.side_effect = PyiCloudAuthRequiredException(
            USERNAME, Mock(spec=Response)
        )
        yield service_mock


@pytest.mark.usefixtures("service_2fa")
async def test_setup_2fa(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test that a 2FA challenge starts reauth and is not reported as a bad password."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.config_entries.flow.async_progress()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    in_progress_flows = hass.config_entries.flow.async_progress()
    assert len(in_progress_flows) == 1
    assert in_progress_flows[0]["context"]["unique_id"] == config_entry.unique_id
    assert "2FA authentication required" in caplog.text
    assert "no longer working" not in caplog.text

    # The reauth flow reuses this session to send and validate the code, so it
    # has to survive the challenge.
    assert config_entry.runtime_data.api is not None


@pytest.mark.usefixtures("service_2fa_failed")
async def test_setup_password_failed(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a rejected password is reported as such, not as a 2FA prompt."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.config_entries.flow.async_progress()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    in_progress_flows = hass.config_entries.flow.async_progress()
    assert len(in_progress_flows) == 1
    assert in_progress_flows[0]["context"]["unique_id"] == config_entry.unique_id
    assert "no longer working" in caplog.text
    assert "2FA authentication required" not in caplog.text
    assert config_entry.runtime_data.api is None


@pytest.mark.usefixtures("service_2fa")
async def test_unique_id_set_on_setup(hass: HomeAssistant) -> None:
    """Test that unique_id is set on setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=None
    )
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.unique_id == USERNAME
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("service_auth_required")
async def test_setup_auth_required(hass: HomeAssistant) -> None:
    """Test that an auth-required login failure starts reauth."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    in_progress_flows = hass.config_entries.flow.async_progress()
    assert len(in_progress_flows) == 1
    assert in_progress_flows[0]["context"]["unique_id"] == config_entry.unique_id


async def test_auth_required_on_first_fetch_fails_authentication(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that losing the session before the first fetch fails setup as auth.

    Only the user can resolve it, so the entry has to end up asking them
    rather than retrying a login that cannot succeed until they are done.
    """
    service_2fa.return_value.requires_2fa = False
    type(service_2fa.return_value).devices = PropertyMock(
        side_effect=PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response))
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # SETUP_ERROR with a reauth flow: Home Assistant owns the reauth lifecycle
    # and stops re-attempting the login while the user is being asked.
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_invalid_token_on_first_fetch_starts_reauth(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that a token rejected on the first fetch asks the user to log in.

    iCloud only rejects a stale stored token when the session is refreshed to
    read the devices, so this surfaces after a successful looking login.
    """
    service_2fa.return_value.requires_2fa = False
    type(service_2fa.return_value).devices = PropertyMock(
        side_effect=PyiCloudFailedLoginException("Invalid authentication token.")
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_2fa_required_exception_on_first_fetch_starts_reauth(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that a 2FA challenge raised by the first fetch asks for a code.

    The challenge arrives when the session is refreshed to read the devices,
    which raises instead of setting requires_2fa, so the exception is the only
    signal that a code is what is missing. The reauth flow has to be told, or
    it reads api.requires_2fa, finds it false and never asks for the code.
    """
    service_2fa.return_value.requires_2fa = False
    service_2fa.return_value.requires_2sa = False
    devices = PropertyMock(
        side_effect=PyiCloud2FARequiredException(USERNAME, Mock(spec=Response))
    )
    type(service_2fa.return_value).devices = devices

    def validate_2fa_code(code: str) -> bool:
        """Clear the challenge, as entering a valid code does."""
        devices.side_effect = None
        devices.return_value = MockDevices([MockDevice(DEVICE)])
        return True

    service_2fa.return_value.validate_2fa_code = Mock(side_effect=validate_2fa_code)

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert len(flows) == 1
    assert flows[0]["step_id"] == "verification_code"

    # The code goes through the session that was kept, not down the
    # two-step-verification path that a false requires_2fa would select.
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"],
        {CONF_VERIFICATION_CODE: "123456", CONF_REQUEST_NEW_CODE: False},
    )
    await hass.async_block_till_done()

    service_2fa.return_value.validate_2fa_code.assert_called_once_with("123456")
    service_2fa.return_value.validate_verification_code.assert_not_called()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    "status",
    [
        AppleAuthError.TWO_FACTOR_REQUIRED,
        AppleAuthError.LOGIN_TOKEN_EXPIRED,
        AppleAuthError.FIND_MY_REAUTH_REQUIRED,
    ],
)
async def test_auth_response_on_first_fetch_starts_reauth(
    hass: HomeAssistant, service_2fa: Mock, status: AppleAuthError
) -> None:
    """Test that an authentication status on the first fetch starts reauth.

    pyicloud only raises a dedicated exception for a 409 carrying an hsa2 body.
    Any other rejection arrives as a plain PyiCloudAPIResponseException, so the
    status has to be inspected rather than the exception type.
    """
    service_2fa.return_value.requires_2fa = False
    type(service_2fa.return_value).devices = PropertyMock(
        side_effect=PyiCloudAPIResponseException(
            "Authentication required for Account.", status
        )
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_other_api_error_on_first_fetch_does_not_start_reauth(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that a non-authentication API error does not ask the user to log in.

    Reauthenticating cannot fix a server-side failure, so prompting for it would
    send the user after credentials that are not the problem.
    """
    service_2fa.return_value.requires_2fa = False
    type(service_2fa.return_value).devices = PropertyMock(
        side_effect=PyiCloudAPIResponseException("Service temporarily unavailable", 503)
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # A server-side failure is transient, so setup has to be retried rather
    # than recorded as an error that never comes back.
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_other_api_error_at_login_is_retried(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that a server-side failure while logging in is retried.

    The 500 that pyicloud groups with the authentication statuses is excluded
    from them on purpose, so it has to land in the retry path rather than
    escape setup as an unexpected error.
    """
    service_2fa.side_effect = PyiCloudAPIResponseException(
        "Internal server error", AppleAuthError.GENERAL_AUTH_ERROR
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_2fa_status_on_first_fetch_asks_for_a_code(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that a 409 status is treated as the challenge it reports.

    The same challenge reaches the integration either as a dedicated exception
    or as a plain response carrying the status, and both have to end up asking
    for a verification code rather than for the password.
    """
    service_2fa.return_value.requires_2fa = False
    service_2fa.return_value.requires_2sa = False
    type(service_2fa.return_value).devices = PropertyMock(
        side_effect=PyiCloudAPIResponseException(
            "Authentication required for Account.",
            AppleAuthError.TWO_FACTOR_REQUIRED,
        )
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The session is kept for the code to go through, as it is for the
    # dedicated exception carrying the same challenge.
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.runtime_data.api is not None
    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert len(flows) == 1
    assert flows[0]["step_id"] == "verification_code"


async def test_service_not_activated_is_not_treated_as_auth_error(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that an inactive iCloud service does not ask the user to log in.

    PyiCloudServiceNotActivatedException subclasses PyiCloudAPIResponseException,
    so it has to keep being handled as a missing service rather than falling
    into the authentication handling.
    """
    service_2fa.return_value.requires_2fa = False
    type(service_2fa.return_value).devices = PropertyMock(
        side_effect=PyiCloudServiceNotActivatedException("Not activated", 400)
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_2fa_required_exception_at_login_starts_reauth(
    hass: HomeAssistant,
) -> None:
    """Test that a 2FA challenge raised while logging in starts reauth.

    authenticate() can raise out of the MFA options request before requires_2fa
    is ever set, leaving no service to ask what is missing.
    """
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_mock.side_effect = PyiCloud2FARequiredException(
            USERNAME, Mock(spec=Response)
        )

        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_password_reauth_reports_a_login_it_cannot_complete(
    hass: HomeAssistant, service_auth_required: Mock
) -> None:
    """Test that a login iCloud keeps rejecting is reported, not raised.

    Discarding the stored session and logging in again is the way out of a
    rejected session, but when that fails as well the user has to be told
    rather than shown an unknown error.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    # The stored session is what iCloud is rejecting, so constructing the
    # service from the reauth form runs into it again.
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response)),
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    "rejection",
    [
        PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response)),
        PyiCloudAPIResponseException(
            "Authentication required for Account.", AppleAuthError.LOGIN_TOKEN_EXPIRED
        ),
    ],
    ids=["exception", "status"],
)
async def test_password_reauth_recovers_from_a_rejected_session(
    hass: HomeAssistant, service_auth_required: Mock, rejection: Exception
) -> None:
    """Test that reauth discards a stored session iCloud is rejecting.

    The service validates the stored session while it is constructed, so the
    password the user submits is never reached until that session is gone.
    The rejection reaches us as a dedicated exception or as a status on a
    plain response, and both have to end up logging in again.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    fresh_api = MagicMock()
    fresh_api.requires_2fa = False
    fresh_api.requires_2sa = False
    fresh_api.devices = MockDevices([MockDevice(DEVICE)])

    def build_service(*args, **kwargs):
        """Reject the stored session, accept a login that does not use it."""
        if kwargs.get("authenticate", True):
            raise rejection
        return fresh_api

    # The account's own login works again once the session has been cleared.
    service_auth_required.side_effect = None
    service_auth_required.return_value = fresh_api

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=build_service,
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: "new-password"}
        )
        await hass.async_block_till_done()

    # The rejected session is dropped and the submitted password is what the
    # login actually uses.
    fresh_api.session.clear_persistence.assert_called_once()
    fresh_api.authenticate.assert_called_once()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_transient_error_in_reauth_keeps_the_stored_session(
    hass: HomeAssistant, service_auth_required: Mock
) -> None:
    """Test that an outage during reauth does not discard the session.

    The stored session carries the trust token that keeps the user from being
    asked for a code again, so it is only worth dropping when iCloud is
    refusing it rather than failing.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]

    built = MagicMock()

    def build_service(*args, **kwargs):
        """Fail the way iCloud does while it is down."""
        if kwargs.get("authenticate", True):
            raise PyiCloudAPIResponseException("Service temporarily unavailable", 503)
        return built

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=build_service,
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    built.session.clear_persistence.assert_not_called()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_reauth_login_challenged_asks_for_a_code(
    hass: HomeAssistant, service_auth_required: Mock
) -> None:
    """Test that a login ending in a challenge asks for the code.

    Logging in again is what re-issues the challenge, so the session that
    login established is the one the code has to go through.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]

    challenged_api = MagicMock()
    challenged_api.requires_2fa = False
    challenged_api.requires_2sa = False
    challenged_api.authenticate.side_effect = PyiCloud2FARequiredException(
        USERNAME, Mock(spec=Response)
    )

    def build_service(*args, **kwargs):
        """Reject the stored session, challenge the fresh login."""
        if kwargs.get("authenticate", True):
            raise PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response))
        return challenged_api

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=build_service,
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    # The challenged session is kept rather than reported as a failure.
    challenged_api.session.clear_persistence.assert_called_once()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "verification_code"


async def test_reauth_login_challenged_by_status_asks_for_a_code(
    hass: HomeAssistant, service_auth_required: Mock
) -> None:
    """Test that a challenge carried by a status asks for the code as well.

    The login is only handed a dedicated exception for a 409 whose body is the
    hsa2 JSON pyicloud looks for. The same challenge on any other body arrives
    as the status on a plain response, and it is still a session to send a
    code through rather than a failure to report.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]

    challenged_api = MagicMock()
    challenged_api.requires_2fa = False
    challenged_api.requires_2sa = False
    challenged_api.authenticate.side_effect = PyiCloudAPIResponseException(
        "Authentication required for Account.", AppleAuthError.TWO_FACTOR_REQUIRED
    )

    def build_service(*args, **kwargs):
        """Reject the stored session, challenge the fresh login."""
        if kwargs.get("authenticate", True):
            raise PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response))
        return challenged_api

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=build_service,
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    # The challenged session is kept rather than reported as a failure.
    challenged_api.session.clear_persistence.assert_called_once()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "verification_code"


async def test_reauth_login_rejected_by_status_is_reported(
    hass: HomeAssistant, service_auth_required: Mock
) -> None:
    """Test that a status that is not a challenge is still reported.

    Only a two-factor status leaves a session worth keeping. Any other
    rejection of the fresh login is a failure the user has to see, so it must
    not be mistaken for a challenge.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]

    rejected_api = MagicMock()
    rejected_api.requires_2fa = False
    rejected_api.requires_2sa = False
    rejected_api.authenticate.side_effect = PyiCloudAPIResponseException(
        "Authentication required for Account.", AppleAuthError.LOGIN_TOKEN_EXPIRED
    )

    def build_service(*args, **kwargs):
        """Reject the stored session, then reject the fresh login too."""
        if kwargs.get("authenticate", True):
            raise PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response))
        return rejected_api

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=build_service,
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_reauth_rejects_a_wrong_password(
    hass: HomeAssistant, service_auth_required: Mock
) -> None:
    """Test that a password iCloud rejects is reported on the password field."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]

    rejected_api = MagicMock()
    rejected_api.authenticate.side_effect = PyiCloudFailedLoginException("nope")

    def build_service(*args, **kwargs):
        """Reject the stored session, then the password."""
        if kwargs.get("authenticate", True):
            raise PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response))
        return rejected_api

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=build_service,
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: "wrong-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_auth_status_at_login_starts_reauth(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that an authentication status while logging in asks the user.

    Only a 409 carrying an hsa2 body reaches us as a dedicated exception, so
    the same rejection during the login arrives as a status on a plain
    response and has to be recognised from it.
    """
    service_2fa.side_effect = PyiCloudAPIResponseException(
        "Authentication required for Account.", AppleAuthError.TWO_FACTOR_REQUIRED
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # No session was established, so there is nothing to send a code through:
    # the user has to log in again even though a code is what iCloud wants.
    assert config_entry.runtime_data.api is None
    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(
            PyiCloud2FARequiredException(USERNAME, Mock(spec=Response)),
            id="challenge_as_exception",
        ),
        pytest.param(
            PyiCloudAPIResponseException(
                "Authentication required for Account.",
                AppleAuthError.TWO_FACTOR_REQUIRED,
            ),
            id="challenge_as_status",
        ),
    ],
)
async def test_a_challenge_that_cannot_send_a_code_is_retried(
    hass: HomeAssistant, service_2fa: Mock, failure: Exception
) -> None:
    """Test that setup is retried when the challenge can deliver no code.

    The options fetch that sets a delivery route up can be refused on its own.
    iCloud still reports the challenge, but nothing can send a code for it, so
    asking leaves the user on a form they cannot complete. Retrying is what
    recovers this, and both shapes the challenge arrives in have to do it.
    """
    service_2fa.return_value.requires_2fa = False
    service_2fa.return_value.requires_2sa = False
    service_2fa.return_value.two_factor_delivery_method = "unknown"
    type(service_2fa.return_value).devices = PropertyMock(side_effect=failure)

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_reauth_challenge_without_a_delivery_route_asks_for_the_password(
    hass: HomeAssistant, service_auth_required: Mock
) -> None:
    """Test that a challenge that can send no code does not open code entry.

    The options fetch that establishes a delivery route can be refused on its
    own. iCloud still reports the challenge, but the code entry form is then a
    dead end. Going back to the password is what recovers it: a fresh login
    raises the challenge again with a route behind it.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]

    challenged_api = MagicMock()
    challenged_api.requires_2fa = False
    challenged_api.requires_2sa = False
    challenged_api.two_factor_delivery_method = "unknown"
    challenged_api.authenticate.side_effect = PyiCloud2FARequiredException(
        USERNAME, Mock(spec=Response)
    )

    def build_service(*args, **kwargs):
        """Reject the stored session, challenge the fresh login."""
        if kwargs.get("authenticate", True):
            raise PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response))
        return challenged_api

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        side_effect=build_service,
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "send_verification_code"}

    # The forced challenge goes with the session, or the retry below reads it
    # and comes straight back here even though the login succeeded.
    working_api = MagicMock()
    working_api.requires_2fa = False
    working_api.requires_2sa = False
    working_api.two_factor_delivery_method = "unknown"
    working_api.devices = MockDevices([MockDevice(DEVICE)])

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        return_value=working_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.ABORT


async def test_reauth_device_fetch_rejected_as_a_failed_login_is_reported(
    hass: HomeAssistant, service_auth_required: Mock
) -> None:
    """Test that a rejected token from the device fetch is handled.

    Reading the devices refreshes the session, and a stored token iCloud has
    since invalidated is rejected there as PyiCloudFailedLoginException.
    Without it in the handled set the step ends on an unhandled exception,
    leaving the user with no way back to the password.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]

    rejected_api = MagicMock()
    rejected_api.requires_2fa = False
    rejected_api.requires_2sa = False
    rejected_api.two_factor_delivery_method = "trusted_device"
    type(rejected_api).devices = PropertyMock(
        side_effect=PyiCloudFailedLoginException("Invalid authentication token.")
    )

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService",
        return_value=rejected_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
