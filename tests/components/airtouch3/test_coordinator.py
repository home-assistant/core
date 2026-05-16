"""Test the AirTouch 3 coordinator."""

from unittest.mock import patch

from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.components.airtouch3.coordinator import (
    Airtouch3DataUpdateCoordinator,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def test_coordinator_does_not_start_command_worker_at_init(
    hass: HomeAssistant,
) -> None:
    """Test the long-running command worker is not created during setup."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)

    with (
        patch.object(hass, "async_create_task") as create_task,
        patch.object(hass, "async_create_background_task") as create_background_task,
    ):
        Airtouch3DataUpdateCoordinator(hass, entry, "1.1.1.1")

    create_task.assert_not_called()
    create_background_task.assert_not_called()
