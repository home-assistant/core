"""Tests for the Vilfo Router integration setup."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vilfo.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("mac", "identifiers"),
    [
        pytest.param(
            "FF-00-00-00-00-00",
            {(DOMAIN, "testadmin.vilfo.com", "FF-00-00-00-00-00")},
            id="with_mac",
        ),
        pytest.param(
            None,
            {(DOMAIN, "testadmin.vilfo.com", None)},
            id="without_mac",
        ),
    ],
)
async def test_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mac: str | None,
    identifiers: set[tuple[str, str | None]],
) -> None:
    """Test the device registry entry.

    The network MAC connection is only attached when the router reports a MAC;
    a router set up by host may not report one.
    """
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.vilfo.VilfoClient", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.mac = mac
        client.get_board_information.return_value = {
            "version": "1.1.0",
            "bootTime": "2024-01-01T00:00:00+00:00",
        }
        client.get_load.return_value = 30
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers=identifiers)
    assert device_entry == snapshot
