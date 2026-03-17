"""Common fixtures for the Yardian tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pyyardian import OperationInfo, YardianDeviceState

from homeassistant.components.yardian import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME, Platform

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.yardian.async_setup_entry", return_value=True
    ) as patched_setup_entry:
        yield patched_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Provide a mocked config entry."""
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
    """Mock the Yardian client used by the integration and config flow."""
    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient", autospec=True
        ) as client_cls,
        patch(
            "homeassistant.components.yardian.config_flow.AsyncYardianClient",
            autospec=True,
        ) as flow_client_cls,
    ):
        client = client_cls.return_value
        flow_client_cls.return_value = client

        client.fetch_device_state.return_value = YardianDeviceState(
            zones=[["Zone 1", 1], ["Zone 2", 0]],
            active_zones={0},
        )
        client.fetch_oper_info.return_value = OperationInfo(
            iRainDelay=3600,
            iSensorDelay=5,
            iWaterHammerDuration=2,
            iStandby=1,
            fFreezePrevent=1,
        )

        yield client


@pytest.fixture
def sensor_platform_only() -> Generator[None]:
    """Limit the integration setup to the sensor platform for faster tests."""
    with patch("homeassistant.components.yardian.PLATFORMS", [Platform.SENSOR]):
        yield
