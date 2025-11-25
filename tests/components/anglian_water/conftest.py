"""Common fixtures for the Anglian Water tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyanglianwater.meter import SmartMeter
import pytest

from homeassistant.components.anglian_water.const import CONF_ACCOUNT_NUMBER, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME

from .const import ACCESS_TOKEN, ACCOUNT_NUMBER, PASSWORD, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
        },
        unique_id=ACCOUNT_NUMBER,
    )


@pytest.fixture
def mock_smart_meter() -> SmartMeter:
    """Return a mocked Smart Meter."""
    mock = AsyncMock(spec=SmartMeter)
    mock.serial_number = "TESTSN"
    mock.get_yesterday_consumption = 50
    mock.latest_read = 50
    mock.yesterday_water_cost = 0.5
    mock.yesterday_sewerage_cost = 0.5
    return mock


@pytest.fixture
def mock_anglian_water_authenticator() -> Generator[MagicMock]:
    """Mock a Anglian Water authenticator."""
    with (
        patch(
            "homeassistant.components.anglian_water.MSOB2CAuth", autospec=True
        ) as mock_auth_class,
        patch(
            "homeassistant.components.anglian_water.config_flow.MSOB2CAuth",
            new=mock_auth_class,
        ),
    ):
        mock_instance = mock_auth_class.return_value
        mock_instance.account_number = ACCOUNT_NUMBER
        mock_instance.access_token = ACCESS_TOKEN
        mock_instance.refresh_token = ACCESS_TOKEN
        mock_instance.send_login_request.return_value = None
        mock_instance.send_refresh_request.return_value = None
        yield mock_instance


@pytest.fixture
def mock_anglian_water_client(
    mock_smart_meter: SmartMeter, mock_anglian_water_authenticator: MagicMock
) -> Generator[AsyncMock]:
    """Mock a Anglian Water client."""
    # Create a mock instance with our meters and config first.
    with (
        patch(
            "homeassistant.components.anglian_water.AnglianWater", autospec=True
        ) as mock_client_class,
        patch(
            "homeassistant.components.anglian_water.config_flow.AnglianWater",
            new=mock_client_class,
        ),
    ):
        mock_client = mock_client_class.return_value
        mock_client.meters = {mock_smart_meter.serial_number: mock_smart_meter}
        mock_client.account_config = {"meter_type": "SmartMeter"}
        mock_client.updated_data_callbacks = []
        mock_client.validate_smart_meter.return_value = None
        yield mock_client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.anglian_water.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
