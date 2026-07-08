"""Test the EvolvIOT coordinator."""

from unittest.mock import AsyncMock

from pyevolviot import EvolvIOTApiError, EvolvIOTAuthError
import pytest

from homeassistant.components.evolviot.const import DOMAIN
from homeassistant.components.evolviot.coordinator import EvolvIOTDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


def _entity() -> dict:
    """Return a switch entity payload."""
    return {
        "entity_id": "switch.evolviot_switch",
        "domain": "switch",
        "control": {"key": "Power"},
        "device": {
            "id": "Device 1",
            "local_control": {
                "enabled": True,
                "device_secret": "secret",
            },
        },
    }


def _coordinator(hass: HomeAssistant) -> EvolvIOTDataUpdateCoordinator:
    """Return a coordinator."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    coordinator = EvolvIOTDataUpdateCoordinator(hass, AsyncMock(), entry)
    coordinator._store.async_save = AsyncMock()
    coordinator._store.async_load = AsyncMock()
    return coordinator


async def test_load_cache(hass: HomeAssistant) -> None:
    """Test loading cached device data."""
    coordinator = _coordinator(hass)
    payload = {"entities": [_entity()]}
    coordinator._store.async_load.return_value = {"devices_payload": payload}

    await coordinator.async_load_cache()

    assert coordinator._cached_devices_payload == payload


async def test_load_cache_ignores_invalid_data(hass: HomeAssistant) -> None:
    """Test invalid cache data is ignored."""
    coordinator = _coordinator(hass)
    coordinator._store.async_load.return_value = []

    await coordinator.async_load_cache()

    assert coordinator._cached_devices_payload is None


async def test_properties_ignore_invalid_data(hass: HomeAssistant) -> None:
    """Test invalid data returns empty mappings."""
    coordinator = _coordinator(hass)
    coordinator.data = {"entities": [], "states": []}

    assert coordinator.entities == {}
    assert coordinator.states == {}


async def test_entities_for_domain(hass: HomeAssistant) -> None:
    """Test filtering entities by domain."""
    coordinator = _coordinator(hass)
    coordinator.data = {
        "entities": {
            "switch.one": {"domain": "switch"},
            "sensor.one": {"domain": "sensor"},
        }
    }

    assert coordinator.entities_for_domain("switch") == [{"domain": "switch"}]


async def test_update_data_with_cloud_and_local_state(hass: HomeAssistant) -> None:
    """Test coordinator update merges cloud and local state."""
    coordinator = _coordinator(hass)
    coordinator.api.async_get_devices.return_value = {
        "user_id": "user-123",
        "entities": [_entity()],
    }
    coordinator.api.async_get_states.return_value = {
        "states": [
            {
                "entity_id": "switch.evolviot_switch",
                "available": True,
                "state": "off",
            }
        ]
    }
    coordinator.api.async_local_status.return_value = {"Power": 1}

    data = await coordinator._async_update_data()

    assert data["states"]["switch.evolviot_switch"]["state"] == "on"
    assert data["states"]["switch.evolviot_switch"]["raw_value"] == 1
    assert data["states"]["switch.evolviot_switch"]["cloud_available"]
    assert data["states"]["switch.evolviot_switch"]["local_available"]
    coordinator._store.async_save.assert_awaited_once()


async def test_update_data_uses_cached_devices_on_cloud_error(
    hass: HomeAssistant,
) -> None:
    """Test cached metadata is used when cloud metadata fetch fails."""
    coordinator = _coordinator(hass)
    coordinator._cached_devices_payload = {"user_id": "", "entities": [_entity()]}
    coordinator.api.async_get_devices.side_effect = EvolvIOTApiError

    data = await coordinator._async_update_data()

    assert "switch.evolviot_switch" in data["entities"]


async def test_update_data_auth_error(hass: HomeAssistant) -> None:
    """Test auth errors become update failures."""
    coordinator = _coordinator(hass)
    coordinator.api.async_get_devices.side_effect = EvolvIOTAuthError

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_update_data_cloud_error_without_entities(hass: HomeAssistant) -> None:
    """Test cloud errors without cached entities fail the update."""
    coordinator = _coordinator(hass)
    coordinator.api.async_get_devices.side_effect = EvolvIOTApiError

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_local_status_error_returns_unavailable(hass: HomeAssistant) -> None:
    """Test local status errors are converted to unavailable."""
    coordinator = _coordinator(hass)
    coordinator.api.async_local_status.side_effect = EvolvIOTApiError

    assert (
        await coordinator._async_local_device_status("user", "device", "secret") is None
    )


async def test_local_value_for_entity_fallbacks(hass: HomeAssistant) -> None:
    """Test local status value lookup fallbacks."""
    coordinator = _coordinator(hass)
    entity = {
        "control": {"key": "Main Power"},
        "device": {"local_control": {}},
    }

    assert coordinator._local_value_for_entity(entity, {"mainpower": "on"}) == "on"
    assert coordinator._normalize_local_status_key("Main Power!") == "mainpower"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, "on"), (0, "off"), ("true", "on"), ("off", "off")],
)
async def test_apply_local_state(
    hass: HomeAssistant,
    value: int | str,
    expected: str,
) -> None:
    """Test local state normalization."""
    coordinator = _coordinator(hass)
    state: dict = {}

    coordinator._apply_local_state(state, value)

    assert state["state"] == expected
    assert state["raw_value"] == value
