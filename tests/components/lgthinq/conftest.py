"""Configure tests for the LGThinQ integration."""

from typing import Any
import uuid

import pytest

from homeassistant.components.lgthinq.const import (
    CLIENT_PREFIX,
    CONF_CONNECT_CLIENT_ID,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY

from .common import mock_device_info
from .const import (
    AIR_CONDITIONER,
    COOKTOP,
    DEHUMIDIFIER,
    MOCK_COUNTRY,
    MOCK_PAT,
    REFRIGERATOR,
    WASHER,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="country_code")
def country_code_ficture() -> str:
    """Return a mock country code."""
    return MOCK_COUNTRY


@pytest.fixture(name="connect_client_id")
def connect_client_id_fixture() -> str:
    """Return a mock connect client id."""
    return f"{CLIENT_PREFIX}-{uuid.uuid4()!s}"


@pytest.fixture(name="access_token")
def access_token_fixture() -> str:
    """Return a mock connect client id."""
    return MOCK_PAT


@pytest.fixture(name="device_list")
def device_list_fixture() -> list[dict[str, Any]]:
    """Return a mock device list."""
    return [
        mock_device_info(AIR_CONDITIONER),
        mock_device_info(COOKTOP),
        mock_device_info(DEHUMIDIFIER),
        mock_device_info(REFRIGERATOR),
        mock_device_info(WASHER),
    ]


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    country_code: str, connect_client_id: str, access_token: str
) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Test {DOMAIN} entry",
        unique_id=access_token,
        data={
            CONF_COUNTRY: country_code,
            CONF_CONNECT_CLIENT_ID: connect_client_id,
            CONF_ACCESS_TOKEN: access_token,
        },
    )
