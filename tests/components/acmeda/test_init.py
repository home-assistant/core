"""Tests for the Acmeda integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.acmeda.const import ACMEDA_HUB_UPDATE, DOMAIN
from homeassistant.components.acmeda.helpers import update_devices
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_hub_run")
async def test_update_devices_renames_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a roller rename is propagated to the device registry."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    roller = MagicMock()
    roller.id = 1234567890123
    roller.name = "Roller"
    roller.battery = 50
    roller.type = 1
    roller.closed_percent = 50

    hub = mock_config_entry.runtime_data
    hub.api.rollers = {roller.id: roller}

    async_dispatcher_send(hass, ACMEDA_HUB_UPDATE.format(mock_config_entry.entry_id))
    await hass.async_block_till_done()

    roller.name = "Living room blind"
    await update_devices(hass, mock_config_entry, hub.api.rollers)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1234567890123"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Living room blind"
