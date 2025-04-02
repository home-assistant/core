"""Conftest."""

from unittest.mock import patch

from kat_bulgaria.errors import KatError, KatErrorType
import pytest

# region py_kat_bulgaria


@pytest.fixture(name="validate_credentials")
def mock_validate_credentials():
    """Mock validate credentials."""
    with patch(
        "kat_bulgaria.kat_api_client.KatApiClient.validate_credentials"
    ) as mock_validate_credentials:
        mock_validate_credentials.return_value = True
        yield


@pytest.fixture(name="validate_credentials_error_egn")
def mock_validate_credentials_error_egn():
    """Mock validate credentials."""
    with patch(
        "kat_bulgaria.kat_api_client.KatApiClient.validate_credentials"
    ) as mock_validate_credentials:
        mock_validate_credentials.side_effect = KatError(
            KatErrorType.VALIDATION_EGN_INVALID, "error text"
        )
        yield


@pytest.fixture(name="validate_credentials_error_license")
def mock_validate_credentials_error_license():
    """Mock validate credentials."""
    with patch(
        "kat_bulgaria.kat_api_client.KatApiClient.validate_credentials"
    ) as mock_validate_credentials:
        mock_validate_credentials.side_effect = KatError(
            KatErrorType.VALIDATION_EGN_INVALID, "error text"
        )
        yield


@pytest.fixture(name="validate_credentials_error_notfoundonline")
def mock_validate_credentials_error():
    """Mock validate credentials."""
    with patch(
        "kat_bulgaria.kat_api_client.KatApiClient.validate_credentials"
    ) as mock_validate_credentials:
        mock_validate_credentials.side_effect = KatError(
            KatErrorType.VALIDATION_USER_NOT_FOUND_ONLINE, "error text"
        )
        yield


@pytest.fixture(name="validate_credentials_api_timeout")
def mock_validate_credentials_api_timeout():
    """Mock validate credentials."""
    with patch(
        "kat_bulgaria.kat_api_client.KatApiClient.validate_credentials"
    ) as mock_validate_credentials:
        mock_validate_credentials.side_effect = KatError(
            KatErrorType.API_TIMEOUT, "error text"
        )
        yield


@pytest.fixture(name="validate_credentials_api_errorreadingdata")
def mock_validate_credentials_api_errorreadingdata():
    """Mock validate credentials."""
    with patch(
        "kat_bulgaria.kat_api_client.KatApiClient.validate_credentials"
    ) as mock_validate_credentials:
        mock_validate_credentials.side_effect = KatError(
            KatErrorType.API_ERROR_READING_DATA, "error text"
        )
        yield


@pytest.fixture(name="validate_credentials_api_invalidschema")
def mock_validate_credentials_api_invalidschema():
    """Mock validate credentials."""
    with patch(
        "kat_bulgaria.kat_api_client.KatApiClient.validate_credentials"
    ) as mock_validate_credentials:
        mock_validate_credentials.side_effect = KatError(
            KatErrorType.API_INVALID_SCHEMA, "error text"
        )
        yield


@pytest.fixture(name="validate_credentials_api_toomanyrequests")
def mock_validate_credentials_api_toomanyrequests():
    """Mock validate credentials."""
    with patch(
        "kat_bulgaria.kat_api_client.KatApiClient.validate_credentials"
    ) as mock_validate_credentials:
        mock_validate_credentials.side_effect = KatError(
            KatErrorType.API_TOO_MANY_REQUESTS, "error text"
        )
        yield


@pytest.fixture(name="validate_credentials_api_unknownerror")
def mock_validate_credentials_api_unknownerror():
    """Mock validate credentials."""
    with patch(
        "kat_bulgaria.kat_api_client.KatApiClient.validate_credentials"
    ) as mock_validate_credentials:
        mock_validate_credentials.side_effect = KatError(
            KatErrorType.API_UNKNOWN_ERROR, "error text"
        )
        yield


# endregion

# region hass_kat_bulgaria


@pytest.fixture(name="katclient_get_obligations_success_none")
def katclient_get_obligations_success_none():
    """Mock get obligations."""
    with patch(
        "homeassistant.components.kat_bulgaria.kat_client.KatClient.get_obligations"
    ) as mock_get_obligations:
        mock_get_obligations.return_value = []
        yield


@pytest.fixture(name="katclient_get_obligations_usernotfoundonline")
def katclient_get_obligations_usernotfoundonline():
    """Mock get obligations."""
    with patch(
        "homeassistant.components.kat_bulgaria.kat_client.KatClient.get_obligations"
    ) as mock_get_obligations:
        mock_get_obligations.side_effect = KatError(
            KatErrorType.VALIDATION_USER_NOT_FOUND_ONLINE, "error text"
        )
        yield


@pytest.fixture(name="katclient_get_obligations_api_timeout")
def katclient_get_obligations_api_timeout():
    """Mock get obligations."""
    with patch(
        "homeassistant.components.kat_bulgaria.kat_client.KatClient.get_obligations"
    ) as mock_get_obligations:
        mock_get_obligations.side_effect = KatError(
            KatErrorType.API_TIMEOUT, "error text"
        )
        yield


@pytest.fixture(name="katclient_get_obligations_api_errorreadingdata")
def katclient_get_obligations_api_errorreadingdata():
    """Mock get obligations."""
    with patch(
        "homeassistant.components.kat_bulgaria.kat_client.KatClient.get_obligations"
    ) as mock_get_obligations:
        mock_get_obligations.side_effect = KatError(
            KatErrorType.API_ERROR_READING_DATA, "error text"
        )
        yield


@pytest.fixture(name="katclient_get_obligations_api_invalidschema")
def katclient_get_obligations_api_invalidschema():
    """Mock get obligations."""
    with patch(
        "homeassistant.components.kat_bulgaria.kat_client.KatClient.get_obligations"
    ) as mock_get_obligations:
        mock_get_obligations.side_effect = KatError(
            KatErrorType.API_INVALID_SCHEMA, "error text"
        )
        yield


@pytest.fixture(name="katclient_get_obligations_api_unknownerror")
def katclient_get_obligations_api_unknownerror():
    """Mock get obligations."""
    with patch(
        "homeassistant.components.kat_bulgaria.kat_client.KatClient.get_obligations"
    ) as mock_get_obligations:
        mock_get_obligations.side_effect = KatError(
            KatErrorType.API_UNKNOWN_ERROR, "error text"
        )
        yield


@pytest.fixture(name="katclient_get_obligations_api_toomanyrequests")
def katclient_get_obligations_api_toomanyrequests():
    """Mock get obligations."""
    with patch(
        "homeassistant.components.kat_bulgaria.kat_client.KatClient.get_obligations"
    ) as mock_get_obligations:
        mock_get_obligations.side_effect = KatError(
            KatErrorType.API_TOO_MANY_REQUESTS, "error text"
        )
        yield


# endregion
