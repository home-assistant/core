"""Tests for IHC event platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.ihc.const import CONF_INFO, DOMAIN, IHC_CONTROLLER
from homeassistant.components.ihc.event import IHCButtonEventEntity, setup_platform
from homeassistant.core import HomeAssistant

CONTROLLER_ID = "controller_1"
IHC_ID = 12345


def _make_product(
    group: str = "Living room",
    product_id: int = 100,
    address_channel: int | None = 1,
) -> dict:
    return {
        "id": product_id,
        "name": "Test Button",
        "note": "",
        "position": "Wall",
        "model": "0x4103",
        "group": group,
        "address_channel": address_channel,
    }


def _make_discovery_info(
    name: str = "test_button",
    ihc_id: int = IHC_ID,
    product: dict | None = None,
) -> dict:
    return {
        name: {
            "ihc_id": ihc_id,
            "ctrl_id": CONTROLLER_ID,
            "product": product or _make_product(),
            "product_cfg": {},
        }
    }


@pytest.fixture
def mock_controller() -> MagicMock:
    """Return a mock IHC controller."""
    return MagicMock()


def test_setup_platform_creates_entities(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test setup_platform adds one IHCButtonEventEntity per discovery entry."""
    hass.data[DOMAIN] = {
        CONTROLLER_ID: {IHC_CONTROLLER: mock_controller, CONF_INFO: False}
    }

    added: list = []
    setup_platform(hass, {}, added.extend, _make_discovery_info())

    assert len(added) == 1
    assert isinstance(added[0], IHCButtonEventEntity)


def test_setup_platform_no_discovery_info(hass: HomeAssistant) -> None:
    """Test setup_platform exits early when discovery_info is None."""
    added: list = []
    setup_platform(hass, {}, added.extend, None)
    assert added == []


def test_entity_name_with_address_channel(mock_controller: MagicMock) -> None:
    """Test name is formatted as {group}_{product_id}_{channel:02d}."""
    product = _make_product(group="Office", product_id=999, address_channel=1)
    entity = IHCButtonEventEntity(
        mock_controller, CONTROLLER_ID, "fallback", IHC_ID, product
    )
    assert entity.name == "Office_999_01"


def test_entity_name_channel_zero_padded(mock_controller: MagicMock) -> None:
    """Test that address_channel is zero-padded to two digits."""
    product = _make_product(address_channel=6)
    entity = IHCButtonEventEntity(
        mock_controller, CONTROLLER_ID, "fallback", IHC_ID, product
    )
    assert entity.name.endswith("_06")


def test_entity_name_fallback_without_address_channel(
    mock_controller: MagicMock,
) -> None:
    """Test name falls back to the auto_setup default when no address_channel."""
    product = _make_product(address_channel=None)
    entity = IHCButtonEventEntity(
        mock_controller, CONTROLLER_ID, "fallback_name", IHC_ID, product
    )
    assert entity.name == "fallback_name"


def test_entity_icon(mock_controller: MagicMock) -> None:
    """Test entity icon is mdi:light-switch."""
    entity = IHCButtonEventEntity(mock_controller, CONTROLLER_ID, "name", IHC_ID)
    assert entity.icon == "mdi:light-switch"


def test_entity_event_types(mock_controller: MagicMock) -> None:
    """Test entity declares only the 'pressed' event type."""
    entity = IHCButtonEventEntity(mock_controller, CONTROLLER_ID, "name", IHC_ID)
    assert entity.event_types == ["pressed"]


def test_on_ihc_change_true_schedules_job(mock_controller: MagicMock) -> None:
    """Test that a True value schedules a press handler on the HA event loop."""
    entity = IHCButtonEventEntity(
        mock_controller, CONTROLLER_ID, "name", IHC_ID, _make_product()
    )
    entity.hass = MagicMock()
    entity.on_ihc_change(IHC_ID, True)
    entity.hass.add_job.assert_called_once_with(entity._handle_press)


def test_on_ihc_change_false_does_not_schedule(mock_controller: MagicMock) -> None:
    """Test that a False value (button release) does not schedule any job."""
    entity = IHCButtonEventEntity(
        mock_controller, CONTROLLER_ID, "name", IHC_ID, _make_product()
    )
    entity.hass = MagicMock()
    entity.on_ihc_change(IHC_ID, False)
    entity.hass.add_job.assert_not_called()


def test_handle_press_fires_pressed_event(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test that _handle_press triggers a pressed event and writes state."""
    hass.data[DOMAIN] = {
        CONTROLLER_ID: {IHC_CONTROLLER: mock_controller, CONF_INFO: False}
    }
    entity = IHCButtonEventEntity(
        mock_controller, CONTROLLER_ID, "name", IHC_ID, _make_product()
    )
    entity.hass = hass
    with patch.object(entity, "async_write_ha_state") as mock_write:
        entity._handle_press()
    assert entity.state_attributes[ATTR_EVENT_TYPE] == "pressed"
    assert entity.state is not None
    mock_write.assert_called_once()
