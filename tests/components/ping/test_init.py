"""Test init of ping component."""

from unittest.mock import AsyncMock, MagicMock, patch

from icmplib import Host, SocketPermissionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import device_registry as dr


@pytest.mark.usefixtures("patch_setup")
async def test_config_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test for setup success."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_device_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test for device migration."""
    config_entry.add_to_hass(hass)

    old_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(HOMEASSISTANT_DOMAIN, config_entry.entry_id)},
    )

    assert config_entry.minor_version == 1

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(config_entry.domain, config_entry.entry_id)},
    )

    assert device is not None
    assert device.id == old_device.id
    assert device.config_entry_id == config_entry.entry_id
    assert config_entry.minor_version == 2


@pytest.mark.parametrize(
    ("socket_side_effect", "icmplib_privileged", "subprocess_calls"),
    [
        pytest.param([None], [True], 0, id="privileged"),
        pytest.param(
            [SocketPermissionError(False), None],
            [False],
            0,
            id="unprivileged",
        ),
        pytest.param(
            [SocketPermissionError(True), SocketPermissionError(False)],
            [],
            1,
            id="no_socket",
        ),
    ],
)
async def test_icmp_privilege_detection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_ping: Host,
    socket_side_effect: list[Exception | None],
    icmplib_privileged: list[bool],
    subprocess_calls: int,
) -> None:
    """Test the host is pinged with icmplib or the binary based on socket privileges."""
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.ping.async_ping",
            side_effect=socket_side_effect,
        ),
        patch(
            "homeassistant.components.ping.helpers.async_ping",
            return_value=patch_ping,
        ) as mock_icmplib_ping,
        patch(
            "asyncio.create_subprocess_exec",
            return_value=MagicMock(
                returncode=1, communicate=AsyncMock(return_value=(b"", b""))
            ),
        ) as mock_subprocess,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert [
        call.kwargs["privileged"] for call in mock_icmplib_ping.call_args_list
    ] == icmplib_privileged
    assert mock_subprocess.call_count == subprocess_calls
