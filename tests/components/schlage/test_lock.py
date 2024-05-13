"""Test schlage lock."""

from datetime import timedelta
from unittest.mock import Mock

from pyschlage.exceptions import UnknownError

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


async def test_lock_device_registry(
    hass: HomeAssistant, mock_added_config_entry: ConfigEntry
) -> None:
    """Test lock is added to device registry."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={("schlage", "test")})
    assert device.model == "<model-name>"
    assert device.sw_version == "1.0"
    assert device.name == "Vault Door"
    assert device.manufacturer == "Schlage"


async def test_lock_services(
    hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
) -> None:
    """Test lock services."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        service_data={ATTR_ENTITY_ID: "lock.vault_door"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.lock.assert_called_once_with()

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        service_data={ATTR_ENTITY_ID: "lock.vault_door"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.unlock.assert_called_once_with()

    await hass.config_entries.async_unload(mock_added_config_entry.entry_id)


async def test_changed_by(
    hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
) -> None:
    """Test population of the changed_by attribute."""
    mock_lock.last_changed_by.reset_mock()
    mock_lock.last_changed_by.return_value = "access code - foo"

    # Make the coordinator refresh data.
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    mock_lock.last_changed_by.assert_called_once_with([])

    lock_device = hass.states.get("lock.vault_door")
    assert lock_device is not None
    assert lock_device.attributes.get("changed_by") == "access code - foo"


async def test_changed_by_uses_previous_logs_on_failure(
    hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
) -> None:
    """Test that a failure to load logs is not terminal."""
    mock_lock.last_changed_by.reset_mock()
    mock_lock.last_changed_by.return_value = "thumbturn"
    mock_lock.logs.side_effect = UnknownError("Cannot load logs")

    # Make the coordinator refresh data.
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    mock_lock.last_changed_by.assert_called_once_with([])

    lock_device = hass.states.get("lock.vault_door")
    assert lock_device is not None
    assert lock_device.attributes.get("changed_by") == "thumbturn"
