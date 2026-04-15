"""Init tests for stips_iru1."""

from unittest.mock import patch

from homeassistant.components.stips_iru1 import DOMAIN
from homeassistant.components.stips_iru1.const import PLATFORMS


async def test_async_setup_entry_forwards_only_climate(hass, MockConfigEntry):
    """Test integration forwards only the climate platform for initial core PR scope."""
    entry = MockConfigEntry(
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
