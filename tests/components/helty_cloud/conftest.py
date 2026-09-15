"""Common fixtures for the Helty Flow Cloud tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyheltycloud import HeltyDevice, HeltyState, VmcMode
import pytest

from homeassistant.components.helty_cloud.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

EMAIL = "user@example.com"
PASSWORD = "hunter2"
DEVICE_NAME = "VMC Soggiorno"
SERIAL = "64000175853003"
BOARD_SERIAL = "DCB4D9A8C966"

DEVICE = HeltyDevice(
    serial_number=SERIAL,
    board_serial=BOARD_SERIAL,
    name=DEVICE_NAME,
    model="1VMC01012B FlowPLUS",
    firmware="1.2.3",
)


def make_state(mode: VmcMode = VmcMode.SPEED_1) -> HeltyState:
    """Build a representative state, reported just now."""
    return HeltyState(
        mode=mode,
        temperature_indoor=30.8,
        temperature_outdoor=37.4,
        humidity=38.5,
        fan_supply=17,
        fan_exhaust=15,
        alarms="0000000000000000",
        timestamp=int(dt_util.utcnow().timestamp() * 1000),
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.helty_cloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_helty_cloud() -> Generator[AsyncMock]:
    """Mock the cloud client at both the integration and config flow import sites."""
    with (
        patch(
            "homeassistant.components.helty_cloud.HeltyCloud",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.helty_cloud.config_flow.HeltyCloud",
            new=mock_client,
        ),
    ):
        # The panel keeps the mode it was last told, so a read back after a
        # command reflects it, as the real one does.
        panel = {"mode": VmcMode.SPEED_1}

        async def set_mode_verified(
            device: HeltyDevice, mode: VmcMode, attempts: int = 3
        ) -> HeltyState:
            panel["mode"] = mode
            return make_state(mode)

        client = mock_client.return_value
        client.get_devices.return_value = [DEVICE]
        client.set_mode_verified.side_effect = set_mode_verified
        # Polls read; only the confirmation after a command wakes the panel.
        client.get_last_telemetry.side_effect = lambda serial: make_state(panel["mode"])
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a configured Helty Flow Cloud entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
        unique_id=EMAIL,
        entry_id="01HHHHHHHHHHHHHHHHHHHHHHHH",
    )
