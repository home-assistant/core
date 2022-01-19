"""Test the GitHub init file."""
from pytest import LogCaptureFixture

from homeassistant.components.github import async_cleanup_device_registry
from homeassistant.components.github.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, mock_device_registry


async def test_device_registry_cleanup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: LogCaptureFixture,
) -> None:
    """Test that we remove untracked repositories from the decvice registry."""
    registry = mock_device_registry(hass)

    device = registry.async_get_or_create(
        identifiers={(DOMAIN, "test/repository")},
        config_entry_id=mock_config_entry.entry_id,
    )

    assert registry.async_get_device({(DOMAIN, "test/repository")}) == device
    await async_cleanup_device_registry(hass, mock_config_entry)

    assert (
        f"Unlinking device {device.id} for untracked repository test/repository from config entry {mock_config_entry.entry_id}"
        in caplog.text
    )
    assert registry.async_get_device({(DOMAIN, "test/repository")}) is None
