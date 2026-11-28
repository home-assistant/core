"""Fixtures for BroadLink Magic tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from broadlink_magic import (
    DiscoveredRMMax,
    Family,
    ImportedDevice,
    ImportedGroup,
    ImportedScene,
    RMProfile,
    Room,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.broadlink_magic_home.const import DOMAIN
from homeassistant.components.broadlink_magic_home.helpers import family_to_entry_data


@pytest.fixture
def family() -> Family:
    """Return an imported family with two gateways and two remotes."""
    return Family(
        family_id="family-1",
        name="Test home",
        bletoken="00010203",
        token="00112233445566778899aabbccddeeff",
        rooms=[Room(0, "Whole home"), Room(1, "Living room")],
        devices=[
            ImportedDevice(
                did="00000000000000000000aabbccddeeff",
                pid="0000000000000000000000008baf0000",
                name="RM Max 1",
                mac="aabbccddeeff",
            ),
            ImportedDevice(
                did="00000000000000000000112233445566",
                pid="0000000000000000000000008baf0000",
                name="RM Max 2",
                mac="112233445566",
            ),
            ImportedDevice(
                did="00000000000000000000aabbccddeeff",
                pid="",
                name="Television",
                sdid="aabbccddeeff_1",
                spid="0000000000000000000000002baf0000",
                short_addr=4660,
                is_rm_child=True,
                rm_profile=RMProfile.TV,
            ),
            ImportedDevice(
                did="00000000000000000000112233445566",
                pid="",
                name="Set-top box",
                sdid="112233445566_1",
                spid="0000000000000000000000002caf0000",
                short_addr=4661,
                is_rm_child=True,
                rm_profile=RMProfile.STB,
            ),
            ImportedDevice(
                did="00000000000000000000aabbccddeeff",
                pid="0000000000000000000000008baf0000",
                name="Air conditioner",
                sdid="aabbccddeeff_2",
                spid="0000000000000000000000008fab0000",
                short_addr=6,
                ble_category="BLEAC",
                room_id=0,
                is_rm_child=True,
                rm_profile=RMProfile.AC,
            ),
            ImportedDevice(
                did="00000000000000000000aabbccddeeff",
                pid="",
                name="Lamp",
                sdid="aabbccddeeff_3",
                spid="0000000000000000000000002aa80000",
                short_addr=257,
                ble_category="LIGHT",
                room_id=1,
            ),
            ImportedDevice(
                did="00000000000000000000aabbccddeeff",
                pid="",
                name="Wall panel",
                sdid="aabbccddeeff_4",
                short_addr=258,
                ble_category="SWITCH",
                channel_count=2,
                channel_names=["Left key", ""],
                room_id=1,
            ),
            ImportedDevice(
                did="00000000000000000000aabbccddeeff",
                pid="",
                name="Curtain",
                sdid="aabbccddeeff_5",
                short_addr=259,
                ble_category="CURTAIN",
                room_id=1,
            ),
        ],
        groups=[
            ImportedGroup(
                group_id=65,
                name="Living room lights",
                ble_category="LIGHT",
                room_id=1,
                room_name="Living room",
                member_ids=["aabbccddeeff_3"],
            ),
            ImportedGroup(
                group_id=256,
                name="All lights",
                ble_category="LIGHT",
                room_id=1,
                room_name="Living room",
                member_ids=[],
            ),
        ],
        scenes=[ImportedScene("193", "Movie", 1, "Living room")],
    )


@pytest.fixture
def gateways() -> list[DiscoveredRMMax]:
    """Return two discovered RM Max gateways."""
    return [
        DiscoveredRMMax("192.0.2.10", "aabbccddeeff", 0xAF8B, "RM Max 1"),
        DiscoveredRMMax("192.0.2.11", "112233445566", 0xAF8B, "RM Max 2"),
    ]


@pytest.fixture
def config_entry(family: Family, gateways: list[DiscoveredRMMax]) -> MockConfigEntry:
    """Return a BroadLink Magic config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=family.name,
        unique_id=f"{family.family_id}",
        data={
            **family_to_entry_data(family, gateways),
        },
    )


@pytest.fixture(autouse=True)
def mock_send() -> Generator[AsyncMock]:
    """Avoid real UDP control in tests."""
    with patch(
        "broadlink_magic.GatewaySet.send_remote_payloads",
        new_callable=AsyncMock,
        return_value=2,
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_gateway_listener() -> Generator[MagicMock]:
    """Avoid binding the fixed gateway UDP port in component tests."""
    manager = MagicMock()
    manager.registry.sendto = MagicMock()
    manager.async_unregister_entry = AsyncMock()
    manager.async_release_flow = AsyncMock()
    getter = AsyncMock(return_value=manager)
    with (
        patch(
            "homeassistant.components.broadlink_magic_home.async_get_gateway_listener",
            getter,
        ),
        patch(
            "homeassistant.components.broadlink_magic_home.config_flow.async_get_gateway_listener",
            getter,
        ),
    ):
        yield manager
