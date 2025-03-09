"""Test helpers for FYTA."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fyta_cli.fyta_models import Credentials, Plant
import pytest

from homeassistant.components.fyta.const import CONF_EXPIRATION, DOMAIN as FYTA_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME

from .const import ACCESS_TOKEN, EXPIRATION, PASSWORD, USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=FYTA_DOMAIN,
        title="fyta_user",
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_EXPIRATION: EXPIRATION,
        },
        minor_version=2,
        entry_id="ce5f5431554d101905d31797e1232da8",
    )


@pytest.fixture
def mock_fyta_connector():
    """Build a fixture for the Fyta API that connects successfully and returns one device."""

    plants: dict[int, Plant] = {
        0: Plant.from_dict(load_json_object_fixture("plant_status1.json", FYTA_DOMAIN)),
        1: Plant.from_dict(load_json_object_fixture("plant_status2.json", FYTA_DOMAIN)),
    }

    mock_fyta_connector = AsyncMock()
    mock_fyta_connector.expiration = datetime.fromisoformat(EXPIRATION).replace(
        tzinfo=UTC
    )
    mock_fyta_connector.client = AsyncMock(autospec=True)
    mock_fyta_connector.data = MagicMock()
    mock_fyta_connector.update_all_plants.return_value = plants
    mock_fyta_connector.plant_list = {
        0: "Gummibaum",
        1: "Kakaobaum",
    }

    mock_fyta_connector.login = AsyncMock(
        return_value=Credentials(
            access_token=ACCESS_TOKEN,
            expiration=datetime.fromisoformat(EXPIRATION).replace(tzinfo=UTC),
        )
    )
    with (
        patch(
            "homeassistant.components.fyta.FytaConnector",
            autospec=True,
            return_value=mock_fyta_connector,
        ),
        patch(
            "homeassistant.components.fyta.config_flow.FytaConnector",
            autospec=True,
            return_value=mock_fyta_connector,
        ),
    ):
        yield mock_fyta_connector


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fyta.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_getrandbits():
    """Mock image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield
