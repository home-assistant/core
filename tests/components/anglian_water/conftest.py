"""Common fixtures for the Anglian Water tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyanglianwater.api import API
from pyanglianwater.meter import SmartMeter
import pytest

from homeassistant.components.anglian_water.const import CONF_ACCOUNT_NUMBER, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import ACCESS_TOKEN, ACCOUNT_NUMBER, PASSWORD, USERNAME

from tests.common import MockConfigEntry, async_load_json_object_fixture


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
def mock_smart_meter(freezer: FrozenDateTimeFactory) -> SmartMeter:
    """Return a Smart Meter for testing."""
    # Freeze time to June 2, 2024 so "yesterday" is June 1, matching our test readings
    freezer.move_to("2024-06-02T00:00:00Z")

    meter = SmartMeter("TESTSN")
    meter.readings = [
        {"read_at": "2024-06-01T12:00:00", "consumption": 10, "read": 10},
        {"read_at": "2024-06-01T13:00:00", "consumption": 15, "read": 25},
        {"read_at": "2024-06-01T14:00:00", "consumption": 25, "read": 50},
    ]
    meter.yesterday_water_cost = 0.5
    meter.yesterday_sewerage_cost = 0.5
    return meter


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
        mock_instance.access_token = ACCESS_TOKEN
        mock_instance.refresh_token = ACCESS_TOKEN
        mock_instance.send_login_request.return_value = None
        mock_instance.send_refresh_request.return_value = None
        yield mock_instance


@pytest.fixture
async def mock_anglian_water_client(
    hass: HomeAssistant,
    mock_smart_meter: SmartMeter,
    mock_anglian_water_authenticator: MagicMock,
) -> AsyncGenerator[AsyncMock]:
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
        mock_client.api = AsyncMock(spec=API)
        mock_client.api.get_associated_accounts.return_value = (
            await async_load_json_object_fixture(
                hass, "multi_associated_accounts.json", DOMAIN
            )
        )
        yield mock_client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.anglian_water.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
