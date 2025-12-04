"""Common fixtures for the Yardian tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pyyardian import OperationInfo, YardianDeviceState

from homeassistant.components.yardian import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.yardian.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Define a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="yid123",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_ACCESS_TOKEN: "abc",
            CONF_NAME: "Yardian",
            "yid": "yid123",
            "model": "PRO1902",
            "serialNumber": "SN1",
        },
        title="Yardian Smart Sprinkler",
    )


@pytest.fixture
def mock_yardian_client() -> Generator[AsyncMock]:
    """Define a mocked Yardian client."""
    with patch(
        "homeassistant.components.yardian.AsyncYardianClient", autospec=True
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.fetch_device_state.return_value = YardianDeviceState(
            zones=[["Zone 1", 1], ["Zone 2", 2]],
            active_zones={0},
        )
        mock_client.fetch_oper_info.return_value = OperationInfo(
            iStandby=1, fFreezePrevent=1
        )
        yield mock_client
