"""Test init of ping component."""

from unittest.mock import patch

from icmplib import SocketPermissionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ping.helpers import PingDataICMPLib, PingDataSubProcess
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
    ("ping_side_effect", "privileged", "ping_cls"),
    [
        pytest.param([None], True, PingDataICMPLib, id="privileged"),
        pytest.param(
            [SocketPermissionError(False), None],
            False,
            PingDataICMPLib,
            id="unprivileged",
        ),
        pytest.param(
            [SocketPermissionError(True), SocketPermissionError(False)],
            None,
            PingDataSubProcess,
            id="no_socket",
        ),
    ],
)
async def test_icmp_privilege_detection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ping_side_effect: list[Exception | None],
    privileged: bool | None,
    ping_cls: type[PingDataICMPLib | PingDataSubProcess],
) -> None:
    """Test setup picks icmplib or the ping binary based on socket privileges."""
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.ping.async_ping",
            side_effect=ping_side_effect,
        ) as mock_ping,
        patch(f"{ping_cls.__module__}.{ping_cls.__name__}.async_update"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert [call.kwargs["privileged"] for call in mock_ping.call_args_list] == [
        True,
        False,
    ][: len(ping_side_effect)]
    ping = config_entry.runtime_data.ping
    assert isinstance(ping, ping_cls)
    if ping_cls is PingDataICMPLib:
        assert ping._privileged is privileged
