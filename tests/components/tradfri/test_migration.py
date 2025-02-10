"""Test the tradfri migration tools."""

from unittest.mock import MagicMock

import pytest
from pytradfri.device import Device

from homeassistant.components.tradfri.const import DOMAIN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr

from . import GATEWAY_ID

from tests.common import MockConfigEntry


@pytest.mark.parametrize("device", ["air_purifier"], indirect=True)
async def test_migrate_device_identifier(
    hass: HomeAssistant,
    mock_api_factory: MagicMock,
    device: Device,
) -> None:
    """Test migrate device identifier."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "mock-host",
            "identity": "mock-identity",
            "key": "mock-key",
            "gateway_id": GATEWAY_ID,
        },
    )
    entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, 65551)},  # type: ignore[arg-type]
    )

    assert device_entry.identifiers == {(DOMAIN, 65551)}  # type: ignore[comparison-overlap]

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated_device_entry = device_registry.async_get(device_entry.id)

    assert migrated_device_entry
    assert migrated_device_entry.identifiers == {(DOMAIN, "65551")}
