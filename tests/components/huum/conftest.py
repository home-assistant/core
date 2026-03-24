"""Configuration for Huum tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from huum.const import SaunaStatus
import pytest

from homeassistant.components.huum.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_huum() -> Generator[AsyncMock]:
    """Mock data from the API."""
    huum = AsyncMock()

    with (
        patch(
            "homeassistant.components.huum.config_flow.Huum.status",
            return_value=huum,
        ),
        patch(
            "homeassistant.components.huum.coordinator.Huum.status",
            return_value=huum,
        ),
        patch(
            "homeassistant.components.huum.coordinator.Huum.turn_on",
            return_value=huum,
        ) as turn_on,
        patch(
            "homeassistant.components.huum.coordinator.Huum.toggle_light",
            return_value=huum,
        ) as toggle_light,
    ):
        huum.status = SaunaStatus.ONLINE_NOT_HEATING
        huum.config = 3
        huum.door_closed = True
        huum.temperature = 30
        huum.sauna_name = "Home sauna"
        huum.target_temperature = 80
        huum.payment_end_date = "2026-12-31"
        huum.light = 1
        huum.humidity = 0
        huum.target_humidity = 5
        huum.sauna_config.child_lock = "OFF"
        huum.sauna_config.max_heating_time = 3
        huum.sauna_config.min_heating_time = 0
        huum.sauna_config.max_temp = 110
        huum.sauna_config.min_temp = 40
        huum.sauna_config.max_timer = 0
        huum.sauna_config.min_timer = 0

        def _to_dict() -> dict[str, object]:
            return {
                "status": huum.status,
                "config": huum.config,
                "door_closed": huum.door_closed,
                "temperature": huum.temperature,
                "sauna_name": huum.sauna_name,
                "target_temperature": huum.target_temperature,
                "start_date": None,
                "end_date": None,
                "duration": None,
                "steamer_error": None,
                "payment_end_date": huum.payment_end_date,
                "is_private": None,
                "show_modal": None,
                "light": huum.light,
                "humidity": huum.humidity,
                "target_humidity": huum.target_humidity,
                "remote_safety_state": None,
                "sauna_config": {
                    "child_lock": huum.sauna_config.child_lock,
                    "max_heating_time": huum.sauna_config.max_heating_time,
                    "min_heating_time": huum.sauna_config.min_heating_time,
                    "max_temp": huum.sauna_config.max_temp,
                    "min_temp": huum.sauna_config.min_temp,
                    "max_timer": huum.sauna_config.max_timer,
                    "min_timer": huum.sauna_config.min_timer,
                },
            }

        huum.to_dict = Mock(side_effect=_to_dict)
        huum.turn_on = turn_on
        huum.toggle_light = toggle_light

        yield huum


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.huum.async_setup_entry", return_value=True
    ) as setup_entry_mock:
        yield setup_entry_mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "huum@sauna.org",
            CONF_PASSWORD: "ukuuku",
        },
        entry_id="AABBCC112233",
    )
