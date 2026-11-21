"""Common fixtures for the Sony Songpal tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from songpal.group import GroupState

from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from . import (
    LEADER_ENDPOINT,
    LEADER_LOCATION,
    LEADER_UDN,
    MEMBER_ENDPOINT,
    MEMBER_LOCATION,
    MEMBER_UDN,
    _create_mocked_device,
    _create_mocked_group_control,
    _group_state,
    _setup_songpal,
    _ssdp_info,
)


@pytest.fixture
def mock_devices() -> Generator[dict[str, MagicMock]]:
    """Mock the songpal devices, created on demand by their endpoint."""
    devices: dict[str, MagicMock] = {}

    def _device(endpoint: str) -> MagicMock:
        if endpoint not in devices:
            devices[endpoint] = _create_mocked_device(
                wired_mac=endpoint, endpoint=endpoint
            )
        return devices[endpoint]

    with patch(
        "homeassistant.components.songpal.media_player.Device", side_effect=_device
    ):
        yield devices


@pytest.fixture
def mock_group_controls() -> Generator[dict[str, MagicMock]]:
    """Mock the group controls, created on demand by their UPnP location."""
    group_controls: dict[str, MagicMock] = {}

    def _group_control(location: str) -> MagicMock:
        if location not in group_controls:
            group_controls[location] = _create_mocked_group_control(_group_state())
        return group_controls[location]

    with patch(
        "homeassistant.components.songpal.media_player.GroupControl",
        side_effect=_group_control,
    ):
        yield group_controls


@pytest.fixture
def mock_ssdp(hass: HomeAssistant) -> Generator[list[SsdpServiceInfo]]:
    """Mock the SSDP discovery infos, which tests can change at any time."""
    hass.config.components.add("ssdp")
    ssdp_infos: list[SsdpServiceInfo] = []
    with patch(
        "homeassistant.components.songpal.media_player.ssdp.async_get_discovery_info_by_st",
        side_effect=lambda *_: ssdp_infos,
    ):
        yield ssdp_infos


@pytest.fixture
def leader_state() -> GroupState:
    """Return the group state the leader reports."""
    return _group_state()


@pytest.fixture
def member_state() -> GroupState:
    """Return the group state the member reports."""
    return _group_state()


@pytest.fixture
def friendly_names() -> tuple[str | None, str | None]:
    """Return the UPnP friendly names of the leader and the member."""
    return ("Living room", "Bathroom")


@pytest.fixture
async def mock_group(
    hass: HomeAssistant,
    mock_devices: dict[str, MagicMock],
    mock_group_controls: dict[str, MagicMock],
    mock_ssdp: list[SsdpServiceInfo],
    leader_state: GroupState,
    member_state: GroupState,
    friendly_names: tuple[str | None, str | None],
) -> tuple[MagicMock, MagicMock]:
    """Set up a leader and a member device and return their group controls."""
    leader = mock_group_controls[LEADER_LOCATION] = _create_mocked_group_control(
        leader_state
    )
    member = mock_group_controls[MEMBER_LOCATION] = _create_mocked_group_control(
        member_state
    )
    mock_ssdp.extend(
        [
            _ssdp_info("http://10.0.0.9:80/description.xml", "uuid:other"),
            _ssdp_info(LEADER_LOCATION, LEADER_UDN, friendly_names[0], LEADER_ENDPOINT),
            _ssdp_info(MEMBER_LOCATION, MEMBER_UDN, friendly_names[1], MEMBER_ENDPOINT),
        ]
    )
    await _setup_songpal(hass, "leader", LEADER_ENDPOINT)
    await _setup_songpal(hass, "member", MEMBER_ENDPOINT)
    return leader, member
