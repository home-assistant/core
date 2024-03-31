"""Tests for the LaMetric button platform."""

from unittest.mock import MagicMock

from demetriek import LaMetricConnectionError, LaMetricError
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.lametric.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.usefixtures("init_integration"),
    pytest.mark.freeze_time("2022-09-19 12:07:30"),
]


async def test_button_app_next(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the LaMetric next app button."""
    state = hass.states.get("button.frenck_s_lametric_next_app")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("button.frenck_s_lametric_next_app")
    assert entry
    assert entry.unique_id == "SA110405124500W00BS9-app_next"
    assert entry.entity_category == EntityCategory.CONFIG

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url is None
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }
    assert device_entry.entry_type is None
    assert device_entry.identifiers == {(DOMAIN, "SA110405124500W00BS9")}
    assert device_entry.manufacturer == "LaMetric Inc."
    assert device_entry.model == "LM 37X8"
    assert device_entry.name == "Frenck's LaMetric"
    assert device_entry.sw_version == "2.2.2"
    assert device_entry.hw_version is None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.frenck_s_lametric_next_app"},
        blocking=True,
    )

    assert len(mock_lametric.app_next.mock_calls) == 1
    mock_lametric.app_next.assert_called_with()

    state = hass.states.get("button.frenck_s_lametric_next_app")
    assert state
    assert state.state == "2022-09-19T12:07:30+00:00"


async def test_button_app_previous(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the LaMetric previous app button."""
    state = hass.states.get("button.frenck_s_lametric_previous_app")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("button.frenck_s_lametric_previous_app")
    assert entry
    assert entry.unique_id == "SA110405124500W00BS9-app_previous"
    assert entry.entity_category == EntityCategory.CONFIG

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url is None
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }
    assert device_entry.entry_type is None
    assert device_entry.identifiers == {(DOMAIN, "SA110405124500W00BS9")}
    assert device_entry.manufacturer == "LaMetric Inc."
    assert device_entry.model == "LM 37X8"
    assert device_entry.name == "Frenck's LaMetric"
    assert device_entry.sw_version == "2.2.2"
    assert device_entry.hw_version is None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.frenck_s_lametric_previous_app"},
        blocking=True,
    )

    assert len(mock_lametric.app_previous.mock_calls) == 1
    mock_lametric.app_previous.assert_called_with()

    state = hass.states.get("button.frenck_s_lametric_previous_app")
    assert state
    assert state.state == "2022-09-19T12:07:30+00:00"


async def test_button_dismiss_current_notification(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the LaMetric dismiss current notification button."""
    state = hass.states.get("button.frenck_s_lametric_dismiss_current_notification")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get(
        "button.frenck_s_lametric_dismiss_current_notification"
    )
    assert entry
    assert entry.unique_id == "SA110405124500W00BS9-dismiss_current"
    assert entry.entity_category == EntityCategory.CONFIG

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url is None
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }
    assert device_entry.entry_type is None
    assert device_entry.identifiers == {(DOMAIN, "SA110405124500W00BS9")}
    assert device_entry.manufacturer == "LaMetric Inc."
    assert device_entry.model == "LM 37X8"
    assert device_entry.name == "Frenck's LaMetric"
    assert device_entry.sw_version == "2.2.2"
    assert device_entry.hw_version is None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.frenck_s_lametric_dismiss_current_notification"},
        blocking=True,
    )

    assert len(mock_lametric.dismiss_current_notification.mock_calls) == 1
    mock_lametric.dismiss_current_notification.assert_called_with()

    state = hass.states.get("button.frenck_s_lametric_dismiss_current_notification")
    assert state
    assert state.state == "2022-09-19T12:07:30+00:00"


async def test_button_dismiss_all_notifications(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the LaMetric dismiss all notifications button."""
    state = hass.states.get("button.frenck_s_lametric_dismiss_all_notifications")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get(
        "button.frenck_s_lametric_dismiss_all_notifications"
    )
    assert entry
    assert entry.unique_id == "SA110405124500W00BS9-dismiss_all"
    assert entry.entity_category == EntityCategory.CONFIG

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url is None
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }
    assert device_entry.entry_type is None
    assert device_entry.identifiers == {(DOMAIN, "SA110405124500W00BS9")}
    assert device_entry.manufacturer == "LaMetric Inc."
    assert device_entry.model == "LM 37X8"
    assert device_entry.name == "Frenck's LaMetric"
    assert device_entry.sw_version == "2.2.2"
    assert device_entry.hw_version is None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.frenck_s_lametric_dismiss_all_notifications"},
        blocking=True,
    )

    assert len(mock_lametric.dismiss_all_notifications.mock_calls) == 1
    mock_lametric.dismiss_all_notifications.assert_called_with()

    state = hass.states.get("button.frenck_s_lametric_dismiss_all_notifications")
    assert state
    assert state.state == "2022-09-19T12:07:30+00:00"


async def test_button_error(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test error handling of the LaMetric buttons."""
    mock_lametric.app_next.side_effect = LaMetricError

    with pytest.raises(
        HomeAssistantError, match="Invalid response from the LaMetric device"
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.frenck_s_lametric_next_app"},
            blocking=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("button.frenck_s_lametric_next_app")
    assert state
    assert state.state == "2022-09-19T12:07:30+00:00"


async def test_button_connection_error(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test connection error handling of the LaMetric buttons."""
    mock_lametric.app_next.side_effect = LaMetricConnectionError

    with pytest.raises(
        HomeAssistantError, match="Error communicating with the LaMetric device"
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.frenck_s_lametric_next_app"},
            blocking=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("button.frenck_s_lametric_next_app")
    assert state
    assert state.state == STATE_UNAVAILABLE
