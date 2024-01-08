"""Lamarzocco session fixtures."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

from lmcloud.const import LaMarzoccoModel
import pytest

from homeassistant.components.lamarzocco.const import CONF_MACHINE, DOMAIN
from homeassistant.core import HomeAssistant

from . import USER_INPUT

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry(mock_lamarzocco: MagicMock) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My LaMarzocco",
        domain=DOMAIN,
        data=USER_INPUT | {CONF_MACHINE: mock_lamarzocco.serial_number},
        unique_id=mock_lamarzocco.serial_number,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_lamarzocco: MagicMock
) -> MockConfigEntry:
    """Set up the LaMetric integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture(
    params=[
        LaMarzoccoModel.GS3_AV,
        LaMarzoccoModel.GS3_MP,
        LaMarzoccoModel.LINEA_MICRA,
        LaMarzoccoModel.LINEA_MINI,
    ]
)
def mock_lamarzocco(
    request: pytest.FixtureRequest,
) -> Generator[MagicMock, None, None]:
    """Return a mocked LM client."""
    model_name = request.param

    if model_name == LaMarzoccoModel.GS3_AV:
        serial_number = "GS01234"
        true_model_name = "GS3 AV"
    elif model_name == LaMarzoccoModel.GS3_MP:
        serial_number = "GS01234"
        true_model_name = "GS3 MP"
    elif model_name == LaMarzoccoModel.LINEA_MICRA:
        serial_number = "MR01234"
        true_model_name = "Linea Micra"
    elif model_name == LaMarzoccoModel.LINEA_MINI:
        serial_number = "LM01234"
        true_model_name = "Linea Mini"

    with patch(
        "homeassistant.components.lamarzocco.coordinator.LaMarzoccoClient",
        autospec=True,
    ) as lamarzocco_mock, patch(
        "homeassistant.components.lamarzocco.config_flow.LaMarzoccoClient",
        new=lamarzocco_mock,
    ):
        lamarzocco = lamarzocco_mock.return_value

        lamarzocco.machine_info = {
            "machine_name": serial_number,
            "serial_number": serial_number,
        }

        lamarzocco.model_name = model_name
        lamarzocco.true_model_name = true_model_name
        lamarzocco.machine_name = serial_number
        lamarzocco.serial_number = serial_number

        lamarzocco.firmware_version = "1.1"
        lamarzocco.latest_firmware_version = "1.1"
        lamarzocco.gateway_version = "v2.2-rc0"
        lamarzocco.latest_gateway_version = "v3.1-rc4"

        lamarzocco.current_status = json.loads(
            load_fixture("current_status.json", DOMAIN)
        )
        lamarzocco.config = json.loads(load_fixture("config.json", DOMAIN))
        lamarzocco.statistics = json.loads(load_fixture("statistics.json", DOMAIN))

        lamarzocco.get_all_machines.return_value = [
            (serial_number, model_name),
        ]
        lamarzocco.check_local_connection.return_value = True
        lamarzocco.initialized = False

        lamarzocco.lm_bluetooth = MagicMock()
        lamarzocco.lm_bluetooth.address = "AA:BB:CC:DD:EE:FF"

        yield lamarzocco
