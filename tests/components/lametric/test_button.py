"""Tests for the LaMetric button platform."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.lametric.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_ICON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2022-09-19 12:07:30")
async def test_button_app_next(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric next app button."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    state = hass.states.get("button.frenck_s_lametric_next_app")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:arrow-right-bold"
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


@pytest.mark.freeze_time("2022-09-19 12:07:30")
async def test_button_app_previous(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric previous app button."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    state = hass.states.get("button.frenck_s_lametric_previous_app")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:arrow-left-bold"
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
