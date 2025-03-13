"""Fixtures for Wolflink integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from wolf_comm import (
    EnergyParameter,
    HoursParameter,
    ListItemParameter,
    PercentageParameter,
    PowerParameter,
    Pressure,
    SimpleParameter,
    Temperature,
)

from homeassistant.components.wolflink.const import (
    DEVICE_GATEWAY,
    DEVICE_ID,
    DEVICE_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Wolf SmartSet",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            DEVICE_NAME: "test-device",
            DEVICE_GATEWAY: "5678",
            DEVICE_ID: "1234",
        },
        unique_id="1234",
        version=1,
        minor_version=2,
    )


@pytest.fixture
def mock_wolflink() -> Generator[MagicMock]:
    """Return a mocked wolflink client."""
    with (
        patch(
            "homeassistant.components.wolflink.WolfClient", autospec=True
        ) as wolflink_mock,
        patch(
            "homeassistant.components.wolflink.config_flow.WolfClient",
            new=wolflink_mock,
        ),
    ):
        wolflink = wolflink_mock.return_value

        wolflink.fetch_parameters.return_value = [
            EnergyParameter(6002800000, "Energy Parameter", "Heating", 6005200000),
            ListItemParameter(
                8002800000,
                "List Item Parameter",
                "Heating",
                (["Pump", 0], ["Heating", 1]),
                8005200000,
            ),
            PowerParameter(5002800000, "Power Parameter", "Heating", 5005200000),
            Pressure(4002800000, "Pressure Parameter", "Heating", 4005200000),
            Temperature(3002800000, "Temperature Parameter", "Solar", 3005200000),
            PercentageParameter(
                2002800000, "Percentage Parameter", "Solar", 2005200000
            ),
            HoursParameter(7002800000, "Hours Parameter", "Heating", 7005200000),
            SimpleParameter(1002800000, "Simple Parameter", "DHW", 1005200000),
        ]

        yield wolflink


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wolflink: MagicMock
) -> MockConfigEntry:
    """Set up the Wolflink integration for testing."""
    await setup_integration(hass, mock_config_entry)

    return mock_config_entry
