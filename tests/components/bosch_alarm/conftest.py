"""Define fixtures for Bosch Alarm tests."""

from collections.abc import Callable, Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from bosch_alarm_mode2.const import AREA_ARMING_STATUS, AREA_STATUS
from bosch_alarm_mode2.panel import Area, Panel
import pytest

from homeassistant.components.bosch_alarm.const import (
    CONF_INSTALLER_CODE,
    CONF_USER_CODE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PASSWORD, CONF_PORT

from tests.common import MockConfigEntry


@dataclass
class MockBoschAlarmConfig:
    """Define a class used by bosch_alarm fixtures."""

    model: str
    serial: str
    config: dict
    side_effect: Exception
    updates: list[Callable]

    def process_updates(self) -> None:
        """Process any updates that need to happen."""

        for update in self.updates:
            update()
        self.updates.clear()


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


@pytest.fixture(name="data_areas", scope="package")
def data_areas() -> list[Area]:
    """Define a mocked area config."""
    return {1: Area("Area1", AREA_STATUS.DISARMED)}


@pytest.fixture(name="bosch_alarm_test_data")
def bosch_alarm_test_data_fixture(
    request: pytest.FixtureRequest,
    data_solution_3000: dict,
    data_amax_3000: dict,
    data_b5512: dict,
    data_areas: list[Area],
) -> Generator[MockBoschAlarmConfig]:
    """Define a fixture to set up Bosch Alarm."""
    if request.param == "Solution 3000":
        config = MockBoschAlarmConfig(request.param, None, data_solution_3000, None, [])
    if request.param == "AMAX 3000":
        config = MockBoschAlarmConfig(request.param, None, data_amax_3000, None, [])
    if request.param == "B5512 (US1B)":
        config = MockBoschAlarmConfig(request.param, 1234567890, data_b5512, None, [])

    def area_arm_update(self: Panel, area_id: int, status: int) -> None:
        self.areas[area_id].status = status

    async def area_arm(self: Panel, area_id: int, arm_type: int) -> None:
        if arm_type == AREA_ARMING_STATUS.DISARM:
            self.areas[area_id].status = AREA_STATUS.DISARMED
        if arm_type == self._all_arming_id:
            self.areas[area_id].status = AREA_STATUS.ARMING[0]
            config.updates.append(
                lambda: area_arm_update(self, area_id, AREA_STATUS.ALL_ARMED[0])
            )
        if arm_type == self._partial_arming_id:
            self.areas[area_id].status = AREA_STATUS.ARMING[0]
            config.updates.append(
                lambda: area_arm_update(self, area_id, AREA_STATUS.PART_ARMED[0])
            )

    async def connect(self: Panel, load_selector: int = 0):
        if config.side_effect:
            raise config.side_effect
        self.model = request.param
        self.serial_number = config.serial
        self.areas = data_areas

    with (
        patch(
            "homeassistant.components.bosch_alarm.coordinator.Panel.connect", connect
        ),
        patch(
            "homeassistant.components.bosch_alarm.coordinator.Panel._area_arm", area_arm
        ),
    ):
        yield config


@pytest.fixture(name="bosch_config_entry")
def bosch_config_entry_fixture(
    bosch_alarm_test_data: MockBoschAlarmConfig,
) -> Generator[MockConfigEntry]:
    """Mock config entry for bosch alarm."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="unique_id",
        entry_id=bosch_alarm_test_data.model,
        data={
            CONF_HOST: "0.0.0.0",
            CONF_PORT: 7700,
            CONF_MODEL: bosch_alarm_test_data.model,
            **bosch_alarm_test_data.config,
        },
    )
