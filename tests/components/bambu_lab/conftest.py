"""Common fixtures for the Bambu Lab tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiobambulab import (
    PrinterInfo,
    PrinterModel,
    PrinterState,
    PrintState,
    SpeedProfile,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.bambu_lab.const import (
    CONF_ACCESS_CODE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_HOST

from .const import ACCESS_CODE, HOST, SERIAL_NUMBER


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bambu_lab.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the config entry of a printer."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="X1 Carbon",
        unique_id=SERIAL_NUMBER,
        data={
            CONF_HOST: HOST,
            CONF_SERIAL_NUMBER: SERIAL_NUMBER,
            CONF_ACCESS_CODE: ACCESS_CODE,
        },
    )


@pytest.fixture
def mock_bambu_lab_client_class() -> Generator[MagicMock]:
    """Return the mocked client class, to check how a client is created."""
    with (
        patch(
            "homeassistant.components.bambu_lab.BambuLabClient", autospec=True
        ) as client_mock,
        patch(
            "homeassistant.components.bambu_lab.config_flow.BambuLabClient",
            new=client_mock,
        ),
    ):
        yield client_mock


@pytest.fixture
def mock_bambu_lab_client(mock_bambu_lab_client_class: MagicMock) -> MagicMock:
    """Return a mocked client of a printer that is printing."""
    client = mock_bambu_lab_client_class.return_value
    client.serial = SERIAL_NUMBER
    client.available = True
    client.info = PrinterInfo(
        serial=SERIAL_NUMBER,
        model=PrinterModel.X1C,
        model_name="X1 Carbon",
        firmware_version="01.08.02.00",
        hardware_version="AP05",
    )
    client.state = PrinterState(
        print_state=PrintState.PRINTING,
        job_name="Benchy",
        progress=42,
        remaining_minutes=73,
        current_layer=96,
        total_layers=240,
        nozzle_temperature=220,
        nozzle_target_temperature=220,
        bed_temperature=60,
        bed_target_temperature=60,
        chamber_temperature=38,
        speed_profile=SpeedProfile.STANDARD,
        chamber_light_on=True,
        wifi_signal=-58,
    )
    return client
