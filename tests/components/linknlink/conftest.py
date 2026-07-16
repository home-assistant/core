"""Fixtures for LinknLink tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from aiolinknlink import (
    TYPE_ULTRA2,
    UltraDevice,
    UltraEnvironmentState,
    UltraPositionSubscriptionState,
    UltraPositionUpdate,
    UltraSession,
    UltraTargetPosition,
)
import pytest

from homeassistant.components.linknlink.const import DISPLAY_MODEL, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT

from tests.common import MockConfigEntry

HOST = "192.168.1.8"
MAC = "e0:4b:41:01:67:bb"
PORT = 80

DEVICE = UltraDevice(
    id=MAC,
    ip=HOST,
    port=PORT,
    mac=MAC,
    type_id=TYPE_ULTRA2,
    name=DISPLAY_MODEL,
    model=DISPLAY_MODEL,
)
SESSION = UltraSession(
    device=DEVICE,
    session_key=b"0123456789abcdef",
    auth_status="ok",
)
POSITION_UPDATE = UltraPositionUpdate(
    source_ip=HOST,
    targets=(UltraTargetPosition(x=0.3, y=0.4, z=1.2),),
    received_at=datetime(2026, 7, 14, 12, tzinfo=UTC),
)
POSITION_STATE = UltraPositionSubscriptionState(
    subscribed=True,
    stale=False,
    local_port=25826,
    confirmation_count=1,
    latest_update=POSITION_UPDATE,
    last_subscribed_at=datetime(2026, 7, 14, 11, 59, tzinfo=UTC),
)
ENVIRONMENT_STATE = UltraEnvironmentState(
    device_id=MAC,
    values={
        "temperature": 23.5,
        "humidity": 48.25,
        "illuminance": 325.0,
        "occupancy": True,
        "target_count": 2,
        "persons_in_fenced_zones": 0,
        "wifi_signal": -52,
        "zone_1_presence": False,
        "zone_1_target_counts": 1,
        "zone_2_target_counts": 0,
        "zone_3_target_counts": 0,
        "zone_4_target_counts": 0,
    },
    available_fields=frozenset(
        {
            "temperature",
            "humidity",
            "illuminance",
            "occupancy",
            "target_count",
            "persons_in_fenced_zones",
            "wifi_signal",
            "zone_1_presence",
            "zone_1_target_counts",
            "zone_2_target_counts",
            "zone_3_target_counts",
            "zone_4_target_counts",
        }
    ),
    received_at=datetime(2026, 7, 15, 12, tzinfo=UTC),
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
        client.discover_host.return_value = DEVICE
        client.connect.return_value = SESSION
        client.get_environment_state.return_value = ENVIRONMENT_STATE
        yield client


@pytest.fixture(autouse=True)
def mock_position_subscription() -> Generator[tuple[MagicMock, MagicMock]]:
    """Mock the aiolinknlink local UDP subscription."""
    with patch(
        "homeassistant.components.linknlink.coordinator.UltraPositionSubscription",
        autospec=True,
    ) as subscription_class:
        subscription = subscription_class.return_value
        subscription.state = POSITION_STATE
        subscription.start = AsyncMock()
        subscription.stop = AsyncMock()
        yield subscription_class, subscription


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
        title=DISPLAY_MODEL,
        data={CONF_HOST: HOST, CONF_MAC: MAC, CONF_PORT: PORT},
        unique_id=MAC,
    )
