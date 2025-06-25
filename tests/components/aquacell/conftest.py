"""Common fixtures for the Aquacell tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from aioaquacell import AquacellApi, Softener
import pytest

from homeassistant.components.aquacell.const import (
    CONF_REFRESH_TOKEN_CREATION_TIME,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL

from . import TEST_CONFIG_ENTRY, TEST_CONFIG_ENTRY_WITHOUT_BRAND

from tests.common import MockConfigEntry, load_json_array_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aquacell.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_aquacell_api() -> Generator[MagicMock]:
    """Build a fixture for the Aquacell API that authenticates successfully and returns a single softener."""
    with (
        patch(
            "homeassistant.components.aquacell.AquacellApi",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.aquacell.config_flow.AquacellApi",
            new=mock_client,
        ),
    ):
        mock_aquacell_api: AquacellApi = mock_client.return_value
        mock_aquacell_api.authenticate.return_value = "refresh-token"

        softeners_dict = load_json_array_fixture(
            "aquacell/get_all_softeners_one_softener.json"
        )

        softeners = [Softener(softener) for softener in softeners_dict]
        mock_aquacell_api.get_all_softeners.return_value = softeners

        yield mock_aquacell_api


@pytest.fixture
def mock_config_entry_expired() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Aquacell",
        unique_id=TEST_CONFIG_ENTRY[CONF_EMAIL],
        data=TEST_CONFIG_ENTRY,
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Aquacell",
        unique_id=TEST_CONFIG_ENTRY[CONF_EMAIL],
        data={
            **TEST_CONFIG_ENTRY,
            CONF_REFRESH_TOKEN_CREATION_TIME: datetime.now().timestamp(),
        },
    )


@pytest.fixture
def mock_config_entry_without_brand() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Aquacell",
        unique_id=TEST_CONFIG_ENTRY[CONF_EMAIL],
        data={
            **TEST_CONFIG_ENTRY_WITHOUT_BRAND,
            CONF_REFRESH_TOKEN_CREATION_TIME: datetime.now().timestamp(),
        },
    )
