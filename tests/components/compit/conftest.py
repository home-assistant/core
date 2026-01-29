"""Common fixtures for the Compit tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from compit_inext_api import CompitParameter
import pytest

from homeassistant.components.compit.const import DOMAIN
from homeassistant.const import CONF_EMAIL

from .consts import CONFIG_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT,
        unique_id=CONFIG_INPUT[CONF_EMAIL],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.compit.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_compit_api() -> Generator[AsyncMock]:
    """Mock CompitApiConnector."""
    with patch(
        "homeassistant.components.compit.config_flow.CompitApiConnector.init",
    ) as mock_api:
        yield mock_api


@pytest.fixture
def mock_connector():
    """Mock CompitApiConnector devices."""

    mock_device_1 = MagicMock()
    mock_device_1.definition.name = "Test Device 1"
    mock_device_1.state.params = [
        MagicMock(code="__tr_pracy_pc", value="eco"),
        MagicMock(
            code="__trybpracy", value="de_icing"
        ),  # parameter not relevant for this device, should be ignored
    ]
    mock_device_1.definition.code = 224  # R 900

    mock_device_2 = MagicMock()
    mock_device_2.state.params = [
        MagicMock(code="_jezyk", value="english"),
        MagicMock(code="__aerokonfbypass", value="off"),
    ]
    mock_device_2.definition.code = 223  # Nano Color 2

    mock_device_3 = MagicMock()
    mock_device_3.definition.code = 999  # Unknown Device
    mock_device_3.state = None

    all_devices = {1: mock_device_1, 2: mock_device_2, 3: mock_device_3}

    def mock_get_device(device_id: int):
        return all_devices.get(device_id)

    def get_current_option(device_id: int, parameter_code: CompitParameter):
        return next(
            (
                p
                for p in all_devices[device_id].state.params
                if p.code == parameter_code.value
            ),
            None,
        ).value

    def select_device_option(
        device_id: int, parameter_code: CompitParameter, value: str
    ):
        next(
            p
            for p in all_devices[device_id].state.params
            if p.code == parameter_code.value
        ).value = value
        return True

    mock_instance = MagicMock()
    mock_instance.init = AsyncMock(return_value=True)
    mock_instance.all_devices = all_devices
    mock_instance.get_current_option = MagicMock(side_effect=get_current_option)
    mock_instance.select_device_option = AsyncMock(side_effect=select_device_option)
    mock_instance.update_state = AsyncMock()
    mock_instance.get_device = MagicMock(side_effect=mock_get_device)

    with (
        patch(
            "homeassistant.components.compit.CompitApiConnector",
            return_value=mock_instance,
        ),
        patch(
            "homeassistant.components.compit.coordinator.CompitApiConnector",
            return_value=mock_instance,
        ),
    ):
        yield mock_instance
