"""Test firmware entity defaults and unique IDs."""

from unittest.mock import Mock

import pytest

from homeassistant.components.fibaro.firmware import FirmwareUpdateGuard
from homeassistant.components.fibaro.update import FibaroFirmware
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("channel", "enabled", "unique_id"),
    [
        ("stable", True, "HC3-test_firmware"),
        ("beta", False, "HC3-test_firmware_beta"),
    ],
)
async def test_firmware_entity_defaults(
    hass: HomeAssistant, channel: str, enabled: bool, unique_id: str
) -> None:
    """Stable is enabled and beta is opt-in, without changing registry IDs."""
    entry = Mock()
    entry.data = {
        CONF_URL: "http://example.invalid",
        CONF_USERNAME: "test-user",
        CONF_PASSWORD: "test-password",
    }
    entry.runtime_data.hub_serial = "HC3-test"
    entry.runtime_data.read_fibaro_info.return_value.current_version = "5.220.19"
    entity = FibaroFirmware(hass, entry, channel, FirmwareUpdateGuard())
    assert entity.entity_registry_enabled_default is enabled
    assert entity.unique_id == unique_id
