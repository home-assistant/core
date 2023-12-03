"""Test the FastdotcomDataUpdateCoordindator."""
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.fastdotcom.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_fastdotcom_data_update_coordinator(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the reauth form."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[config_entry.domain][config_entry.entry_id]

    assert coordinator.last_update_success is True

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com",
        side_effect=Exception("Test error"),
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed) is True
