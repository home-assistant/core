"""Define fixtures for Bosch Alarm tests."""

from collections.abc import Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.bosch_alarm.const import (
    CONF_INSTALLER_CODE,
    CONF_USER_CODE,
)
from homeassistant.const import CONF_PASSWORD


@dataclass
class MockBoschAlarmConfig:
    """Define a class used by bosch_alarm fixtures."""

    model: str
    config: dict


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bosch_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="data_solution_3000", scope="package")
def data_solution_3000_fixture() -> dict:
    """Define a testing config for configuring a Solution 3000 panel."""
    return {CONF_USER_CODE: "1234"}


@pytest.fixture(name="data_amax_3000", scope="package")
def data_amax_3000_fixture() -> dict:
    """Define a testing config for configuring an AMAX 3000 panel."""
    return {CONF_INSTALLER_CODE: "1234", CONF_PASSWORD: "1234567890"}


@pytest.fixture(name="data_b5512", scope="package")
def data_b5512_fixture() -> dict:
    """Define a testing config for configuring a B5512 panel."""
    return {CONF_PASSWORD: "1234567890"}


@pytest.fixture(name="bosch_alarm_test_data")
def bosch_alarm_test_data_fixture(
    request: pytest.FixtureRequest,
    data_solution_3000: dict,
    data_amax_3000: dict,
    data_b5512: dict,
) -> Generator[MockBoschAlarmConfig]:
    """Define a fixture to set up Bosch Alarm."""

    async def connect(self, load_selector):
        self.model = request.param

    with (
        patch("bosch_alarm_mode2.panel.Panel.connect", connect),
    ):
        if request.param == "Solution 3000":
            yield MockBoschAlarmConfig(request.param, data_solution_3000)
        if request.param == "AMAX 3000":
            yield MockBoschAlarmConfig(request.param, data_amax_3000)
        if request.param == "B5512 (US1B)":
            yield MockBoschAlarmConfig(request.param, data_b5512)
