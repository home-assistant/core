"""Test the Hunter Douglas Powerview entities."""

from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_MAC

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [3])
async def test_unknown_shade_type_model(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a shade of an unknown type gets its type id as a string model."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)

    # aiopvapi returns the integer type id for shade types it doesn't know
    with patch(
        "aiopvapi.resources.shade.BaseShade.type_name",
        new_callable=PropertyMock,
        return_value=999,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert "999" in {device.model for device in devices}
    assert "non-string value" not in caplog.text
