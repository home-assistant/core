"""Test the ADS entity base class."""

from unittest.mock import MagicMock, patch

from homeassistant.components.ads.const import STATE_KEY_STATE
from homeassistant.components.ads.entity import AdsEntity
from homeassistant.components.ads.hub import AdsHub
from homeassistant.core import HomeAssistant


def test_registers_with_hub() -> None:
    """Test the entity registers itself with the hub on init."""
    hub = MagicMock(spec=AdsHub)

    entity = AdsEntity(hub, "test", "GVL.test")

    hub.register_device.assert_called_once_with(entity)


def test_available() -> None:
    """Test availability reflects whether a state has been received."""
    entity = AdsEntity(MagicMock(spec=AdsHub), "test", "GVL.test")

    assert not entity.available

    entity._state_dict[STATE_KEY_STATE] = 1
    assert entity.available


def test_mark_unavailable_before_added_to_hass() -> None:
    """Test marking unavailable before the entity is added to hass."""
    entity = AdsEntity(MagicMock(spec=AdsHub), "test", "GVL.test")
    entity._state_dict[STATE_KEY_STATE] = 1

    entity.mark_unavailable()

    assert not entity.available


def test_mark_unavailable_schedules_update(hass: HomeAssistant) -> None:
    """Test marking unavailable schedules a state update once added to hass."""
    entity = AdsEntity(MagicMock(spec=AdsHub), "test", "GVL.test")
    entity.hass = hass
    entity._state_dict[STATE_KEY_STATE] = 1

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.mark_unavailable()

    mock_schedule.assert_called_once()
    assert not entity.available
