"""Conftest."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

from kat_bulgaria.data_models import KatObligationApiResponse
from kat_bulgaria.errors import KatError, KatErrorType
import pytest

from homeassistant.components.kat_bulgaria.config_flow import DOMAIN
from homeassistant.components.kat_bulgaria.kat_client import KatClient
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import Awaitable, Callable

from . import EGN_VALID, LICENSE_VALID, MOCK_DATA

from tests.common import MockConfigEntry

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

# region coordinator setup


@pytest.fixture(name="platforms")
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR, Platform.SENSOR]


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(domain=DOMAIN, data=MOCK_DATA, unique_id=EGN_VALID)


@pytest.fixture(name="integration_setup")
async def mock_integration_setup(
    hass: HomeAssistant,
    platforms: list[Platform],
    config_entry: MockConfigEntry,
) -> Callable[[MagicMock], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run(client: MagicMock) -> bool:
        with (
            patch("homeassistant.components.kat_bulgaria.PLATFORMS", platforms),
            patch(
                "homeassistant.components.kat_bulgaria.kat_client.KatClient"
            ) as client_mock,
        ):
            client_mock.return_value = client
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
        return result

    return run


# endregion

# region mock data


def load_obligations(local_path: str):
    """Load the obligations into an object."""
    path = os.path.join(_BASE_DIR, local_path)

    with open(path, encoding="utf-8") as fixture:
        json_data = json.load(fixture)

        api_data = KatObligationApiResponse(json_data)

        response = []
        for og in api_data.obligations_data:
            for ob in og.obligations:
                response.extend([ob])

        return response


@pytest.fixture(name="ok_fine_served")
def ok_fine_served():
    """One served fine JSON."""
    return load_obligations("fixtures/ok_fine_served.json")


@pytest.fixture(name="ok_fine_not_served")
def ok_fine_not_served():
    """One non-served fine JSON."""
    return load_obligations("fixtures/ok_fine_not_served.json")


@pytest.fixture(name="ok_sample_6fines")
def ok_sample_6fines():
    """Sample file with 6 fines."""

    return load_obligations("fixtures/ok_sample_6fines.json")


# endregion

# region KatClient mock


@pytest.fixture(name="client")
def mock_client(hass: HomeAssistant, request: pytest.FixtureRequest) -> MagicMock:
    """Fixture to mock KatClient."""

    mock = KatClient(hass, "test", EGN_VALID, LICENSE_VALID)

    mock.get_obligations = AsyncMock(
        side_effect=[],
    )

    mock.side_effect = mock

    return mock


@pytest.fixture(name="client_fine_served")
def mock_client_fine_served(
    hass: HomeAssistant, request: pytest.FixtureRequest, ok_fine_served: pytest.fixture
) -> MagicMock:
    """Fixture to mock KatClient."""

    mock = KatClient(hass, "test", EGN_VALID, LICENSE_VALID)

    mock.get_obligations = AsyncMock(
        side_effect=ok_fine_served,
    )

    mock.side_effect = mock

    return mock


@pytest.fixture(name="client_api_timeout")
def mock_client_api_timeout(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> MagicMock:
    """Fixture to mock KatClient."""

    mock = KatClient(hass, "test", EGN_VALID, LICENSE_VALID)

    mock.get_obligations = AsyncMock(
        side_effect=KatError(KatErrorType.API_TIMEOUT, "error text"),
    )

    mock.side_effect = mock

    return mock


# endregion
