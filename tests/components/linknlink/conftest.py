"""Fixtures for LinknLink tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiolinknlink import UltraDevice, UltraSession, UltraState, UltraSubDeviceState
import pytest

from homeassistant.components.linknlink.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

HOST = "192.168.1.8"
MAC = "e0:4b:41:01:67:bb"
PORT = 80

DEVICE = UltraDevice(
    id=MAC,
    ip=HOST,
    port=PORT,
    mac=MAC,
    name="eMotion Ultra",
    model="eMotion Ultra",
)
SESSION = UltraSession(
    device=DEVICE,
    session_key=b"0123456789abcdef",
    auth_status="ok",
)
STATE = UltraState(
    device_id=MAC,
    online=True,
    values={
        "detect_position": '[{"x":0.3,"y":0.4,"z":1.2}]',
        "distance": 50,
        "envhumid": 45,
        "envlux": 120,
        "envtemp": 23.5,
        "persons_in_fenced_zones": 1,
        "pir_detected": True,
        "presence": True,
        "target_count": 1,
        "target_distance": 130,
        "wifi_rssi": -42,
    },
    children={
        "radar-1": UltraSubDeviceState(
            did="radar-1",
            name="Radar",
            type="Presence sensor",
            fields={"envtemp": 24.0, "pir_detected": True, "power": True},
        )
    },
    updated_at=dt_util.utcnow(),
)


@pytest.fixture
def mock_linknlink_client() -> Generator[AsyncMock]:
    """Mock the aiolinknlink client."""
    with (
        patch(
            "homeassistant.components.linknlink.UltraClient",
            autospec=True,
        ) as client_class,
        patch(
            "homeassistant.components.linknlink.config_flow.UltraClient",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.connect.return_value = SESSION
        client.refresh.return_value = STATE
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config flow tests from setting up the integration."""
    with patch(
        "homeassistant.components.linknlink.async_setup_entry",
        return_value=True,
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a LinknLink config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="eMotion Ultra",
        data={CONF_HOST: HOST, CONF_MAC: MAC, CONF_PORT: PORT},
        unique_id=MAC,
    )
