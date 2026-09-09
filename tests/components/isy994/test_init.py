"""Test the Universal Devices ISY/IoX integration init."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.isy994.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

MOCK_UUID = "ce:fb:72:31:b7:b9"


async def test_migrate_minor_version_drops_tls(
    hass: HomeAssistant,
) -> None:
    """Test minor migration drops legacy "tls" and seeds verify_ssl."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={
            CONF_HOST: "http://1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            "tls": 1.1,
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert "tls" not in entry.data
    assert entry.data[CONF_VERIFY_SSL] is False


@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_setup_forwards_verify_ssl_to_pyisy(
    hass: HomeAssistant,
    mock_isy: MagicMock,
    verify_ssl: bool,
) -> None:
    """Test the verify_ssl entry option is forwarded to the pyisy ISY constructor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        data={
            CONF_HOST: "https://1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_VERIFY_SSL: verify_ssl,
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.isy994.ISY", return_value=mock_isy
    ) as isy_constructor:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isy_constructor.call_args.kwargs["verify_ssl"] is verify_ssl


async def test_node_device_linked_to_isy_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
) -> None:
    """Test a root node's device is linked to the ISY device via via_device_id."""
    mock_config_entry.add_to_hass(hass)

    node = mock_node(mock_isy, "22 22 22 1", "Test Node", "GenericNode")
    mock_isy.nodes.__iter__.return_value = [("Test Node", node)]

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    isy_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_isy.uuid), mock_config_entry.entry_id
    )
    node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_isy.uuid}_{node.address}"), mock_config_entry.entry_id
    )
    assert isy_device is not None
    assert node_device is not None
    assert node_device.via_device_id == isy_device.id
