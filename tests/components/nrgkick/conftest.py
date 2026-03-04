"""Fixtures for NRGkick integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from nrgkick_api import ConnectorType, GridPhases
import pytest

from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nrgkick.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nrgkick_api(
    mock_info_data: dict[str, Any],
    mock_control_data: dict[str, Any],
    mock_values_data: dict[str, Any],
) -> Generator[AsyncMock]:
    """Mock the NRGkick API client and patch it where used."""
    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI",
            autospec=True,
        ) as mock_api_cls,
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            new=mock_api_cls,
        ),
    ):
        api = mock_api_cls.return_value

        api.test_connection.return_value = True
        api.get_info.return_value = mock_info_data
        api.get_control.return_value = mock_control_data
        api.get_values.return_value = mock_values_data

        api.set_current.return_value = 16.0
        api.set_charge_pause.return_value = 0
        api.set_energy_limit.return_value = 0
        api.set_phase_count.return_value = 3

        yield api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="NRGkick Test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
        },
        entry_id="test_entry_id",
        unique_id="TEST123456",
    )


@pytest.fixture
def mock_info_data() -> dict[str, Any]:
    """Mock device info data."""
    res = load_json_object_fixture("info.json", DOMAIN)
    res["connector"]["type"] = ConnectorType.TYPE2
    res["grid"]["phases"] = GridPhases.L1_L2_L3
    return res


@pytest.fixture
def mock_control_data() -> dict[str, Any]:
    """Mock control data."""
    return load_json_object_fixture("control.json", DOMAIN)


@pytest.fixture
def mock_values_data() -> dict[str, Any]:
    """Mock values data."""
    return load_json_object_fixture("values_sensor.json", DOMAIN)
