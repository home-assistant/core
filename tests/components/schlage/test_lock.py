"""Test schlage lock."""
from unittest.mock import Mock, create_autospec

from pyschlage.lock import Lock
import pytest

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.schlage.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture
def mock_lock():
    """Mock Lock fixture."""
    mock_lock = create_autospec(Lock)
    mock_lock.configure_mock(
        device_id="test",
        name="Vault Door",
        model_name="<model-name>",
        is_locked=False,
        is_jammed=False,
        battery_level=0,
        firmware_version="1.0",
    )
    return mock_lock


@pytest.fixture
async def mock_entry(
    hass: HomeAssistant, mock_pyschlage_auth: Mock, mock_schlage: Mock, mock_lock: Mock
) -> ConfigEntry:
    """Create and add a mock ConfigEntry."""
    mock_schlage.locks.return_value = [mock_lock]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-username", "password": "test-password"},
        entry_id="test-username",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.config_entries.async_domains()
    return entry


async def test_lock_device_registry(
    hass: HomeAssistant, mock_entry: ConfigEntry
) -> None:
    """Test lock is added to device registry."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={("schlage", "test")})
    assert device.model == "<model-name>"
    assert device.sw_version == "1.0"
    assert device.name == "Vault Door"
    assert device.manufacturer == "Schlage"


async def test_lock_services(
    hass: HomeAssistant, mock_lock: Mock, mock_entry: ConfigEntry
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

    await hass.config_entries.async_unload(mock_entry.entry_id)
