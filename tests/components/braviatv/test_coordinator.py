"""Tests for the Bravia TV coordinator."""

from unittest.mock import AsyncMock

from pybravia import BraviaConnectionError
import pytest

from homeassistant.components.braviatv.const import DOMAIN
from homeassistant.components.braviatv.coordinator import BraviaTVCoordinator
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_MAC: "AA:BB:CC:DD:EE:FF",
    CONF_PIN: "1234",
}

MOCK_SYSTEM_INFO = {
    "product": "TV",
    "model": "XR-55A95K",
    "macAddr": "AA:BB:CC:DD:EE:FF",
}

MOCK_INPUTS = [
    {"title": "HDMI 1", "uri": "extInput:hdmi?port=1"},
    {"title": "HDMI 2", "uri": "extInput:hdmi?port=2"},
    {"title": "AV/Component", "uri": "extInput:component?port=1"},
]

MOCK_APPS = [
    {"title": "Netflix", "uri": "com.sony.dtv.com.netflix.ninja"},
    {"title": "YouTube", "uri": "com.sony.dtv.com.google.android.youtube.tv"},
]

MOCK_CHANNELS = [
    {"title": "BBC One", "uri": "tv:dvbt?trip=1.2.3&srvName=BBC+One", "dispNum": "1"},
]


@pytest.fixture
def mock_bravia_client() -> AsyncMock:
    """Return a configured mock BraviaClient instance."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.get_power_status = AsyncMock(return_value="active")
    client.get_system_info = AsyncMock(return_value=MOCK_SYSTEM_INFO)
    client.get_external_status = AsyncMock(return_value=MOCK_INPUTS)
    client.get_app_list = AsyncMock(return_value=MOCK_APPS)
    client.get_content_list_all = AsyncMock(return_value=MOCK_CHANNELS)
    client.get_volume_info = AsyncMock(
        return_value={"volume": 50, "mute": False, "target": "speaker"}
    )
    client.get_playing_info = AsyncMock(return_value={})
    return client


@pytest.fixture
def coordinator(
    hass: HomeAssistant, mock_bravia_client: AsyncMock
) -> BraviaTVCoordinator:
    """Create a coordinator backed by the mock client."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    config_entry.add_to_hass(hass)
    coord = BraviaTVCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_bravia_client,
    )
    coord.connected = True  # skip connect step
    return coord


async def test_sources_populated_when_tv_on(
    coordinator: BraviaTVCoordinator,
) -> None:
    """Source list is populated on the first update when TV is on."""
    await coordinator.async_refresh()

    assert coordinator.is_on is True
    assert coordinator.source_list == ["HDMI 1", "HDMI 2", "AV/Component"]
    assert len(coordinator.source_map) == len(MOCK_INPUTS) + len(MOCK_APPS) + len(
        MOCK_CHANNELS
    )


async def test_sources_populated_when_tv_off(
    coordinator: BraviaTVCoordinator,
    mock_bravia_client: AsyncMock,
) -> None:
    """Source list is populated even when the TV is in standby."""
    mock_bravia_client.get_power_status.return_value = "standby"
    mock_bravia_client.get_content_list_all.return_value = []

    await coordinator.async_refresh()

    assert coordinator.is_on is False
    assert coordinator.source_list == ["HDMI 1", "HDMI 2", "AV/Component"]


async def test_sources_not_populated_on_connection_error(
    coordinator: BraviaTVCoordinator,
    mock_bravia_client: AsyncMock,
) -> None:
    """A connection error during source fetch is handled by the outer error handler."""
    mock_bravia_client.get_power_status.return_value = "standby"
    mock_bravia_client.get_external_status.side_effect = BraviaConnectionError()

    await coordinator.async_refresh()

    assert coordinator.is_on is False
    assert coordinator.source_list == []


async def test_volume_and_playing_not_fetched_when_off(
    coordinator: BraviaTVCoordinator,
    mock_bravia_client: AsyncMock,
) -> None:
    """Volume and playing info are not fetched when TV is off."""
    mock_bravia_client.get_power_status.return_value = "standby"

    await coordinator.async_refresh()

    mock_bravia_client.get_volume_info.assert_not_called()
    mock_bravia_client.get_playing_info.assert_not_called()


async def test_sources_fetched_only_once_while_on(
    coordinator: BraviaTVCoordinator,
    mock_bravia_client: AsyncMock,
) -> None:
    """Sources are not re-fetched on consecutive updates while TV remains on."""
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    mock_bravia_client.get_external_status.assert_called_once()


async def test_sources_repopulated_when_tv_turns_on(
    coordinator: BraviaTVCoordinator,
    mock_bravia_client: AsyncMock,
) -> None:
    """Sources are re-fetched with real device names when TV transitions from standby to on.

    In standby the TV returns generic names ("HDMI 1"). When it powers on it reads
    device names via EDID ("PlayStation 5"). Without re-fetching on this transition,
    the source list would be permanently stuck with the generic standby names.
    """
    mock_bravia_client.get_power_status.side_effect = ["standby", "active"]
    mock_bravia_client.get_content_list_all.side_effect = [[], MOCK_CHANNELS]
    mock_bravia_client.get_external_status.side_effect = [
        MOCK_INPUTS,
        [
            {"title": "PlayStation 5", "uri": "extInput:hdmi?port=1"},
            {"title": "Apple TV", "uri": "extInput:hdmi?port=2"},
            {"title": "AV/Component", "uri": "extInput:component?port=1"},
        ],
    ]

    await coordinator.async_refresh()
    assert coordinator.source_list == ["HDMI 1", "HDMI 2", "AV/Component"]

    await coordinator.async_refresh()
    assert coordinator.source_list == ["PlayStation 5", "Apple TV", "AV/Component"]
    assert mock_bravia_client.get_external_status.call_count == 2


async def test_sources_not_overwritten_when_tv_turns_off(
    coordinator: BraviaTVCoordinator,
    mock_bravia_client: AsyncMock,
) -> None:
    """Sources are not re-fetched when TV transitions from on to standby.

    When the TV is on, real device names are populated ("PlayStation 5"). When it
    enters standby those names should be preserved, not overwritten with the generic
    standby names the TV would return.
    """
    mock_bravia_client.get_power_status.side_effect = ["active", "standby"]
    mock_bravia_client.get_external_status.return_value = [
        {"title": "PlayStation 5", "uri": "extInput:hdmi?port=1"},
        {"title": "Apple TV", "uri": "extInput:hdmi?port=2"},
        {"title": "AV/Component", "uri": "extInput:component?port=1"},
    ]

    await coordinator.async_refresh()
    assert coordinator.source_list == ["PlayStation 5", "Apple TV", "AV/Component"]

    await coordinator.async_refresh()
    assert coordinator.source_list == ["PlayStation 5", "Apple TV", "AV/Component"]
    mock_bravia_client.get_external_status.assert_called_once()


async def test_sources_repopulated_after_explicit_refresh(
    coordinator: BraviaTVCoordinator,
    mock_bravia_client: AsyncMock,
) -> None:
    """async_update_sources resets and fully repopulates source_list."""
    await coordinator.async_refresh()

    await coordinator.async_update_sources()

    assert coordinator.source_list == ["HDMI 1", "HDMI 2", "AV/Component"]
    assert mock_bravia_client.get_external_status.call_count == 2
