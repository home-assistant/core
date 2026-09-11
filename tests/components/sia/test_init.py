"""Test the sia setup process."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.sia.const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_IGNORE_TIMESTAMPS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DOMAIN,
)
from homeassistant.const import CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

CONFIG_ENTRY_DATA = {
    CONF_PORT: 7777,
    CONF_PROTOCOL: "TCP",
    CONF_ACCOUNTS: [
        {
            CONF_ACCOUNT: "ABCDEF",
            CONF_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAA",
            CONF_PING_INTERVAL: 10,
        },
    ],
}
CONFIG_ENTRY_OPTIONS = {
    CONF_ACCOUNTS: {"ABCDEF": {CONF_IGNORE_TIMESTAMPS: False, CONF_ZONES: 1}}
}


@pytest.fixture(autouse=True)
def mock_sia_client() -> Generator[None]:
    """Mock SIAClient so no real socket is opened."""
    with patch("homeassistant.components.sia.hub.SIAClient", autospec=True):
        yield


async def test_entity_device_linked_to_hub_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test an entity's device is linked to its hub device via via_device_id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA,
        options=CONFIG_ENTRY_OPTIONS,
        title="SIA Alarm on port 7777",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "7777_ABCDEF"), config_entry.entry_id
    )
    assert hub_device is not None

    alarm_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{config_entry.entry_id}_ABCDEF_1"), config_entry.entry_id
    )
    assert alarm_device is not None
    assert alarm_device.via_device_id == hub_device.id
