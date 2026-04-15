"""Init tests for stips_iru1."""

from unittest.mock import patch

import pytest

from homeassistant.components.stips_iru1 import (
    DOMAIN,
    StipsIru1RuntimeData,
    async_setup_entry,
)
from homeassistant.components.stips_iru1.const import PLATFORMS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from tests.common import MockConfigEntry


async def test_async_setup_entry_forwards_only_climate(
    hass: HomeAssistant,
) -> None:
    """Test integration forwards only the climate platform for initial core PR scope."""
    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "devices": [
                {
                    "uniqueName": "stips-iru1-98eea1",
                    "name": "IR maze",
                    "remotes": [],
                }
            ]
        },
    )
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        return_value=True,
    ) as mock_forward:
        assert await hass.config_entries.async_setup(entry.entry_id)

    mock_forward.assert_called_once_with(entry, PLATFORMS)
    assert PLATFORMS == ["climate"]
    assert isinstance(entry.runtime_data, StipsIru1RuntimeData)
    assert entry.runtime_data.devices == entry.data["devices"]


async def test_async_setup_entry_raises_for_invalid_devices_data(
    hass: HomeAssistant,
) -> None:
    """Test setup raises a config entry error when devices data is invalid."""
    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN, data={"devices": {"invalid": "shape"}}
    )

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=True,
        ) as mock_forward,
        pytest.raises(ConfigEntryError),
    ):
        await async_setup_entry(hass, entry)

    mock_forward.assert_not_called()
