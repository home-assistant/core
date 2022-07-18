"""Tests for the Elgato Light button platform."""
from unittest.mock import MagicMock

from elgato import ElgatoError
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.elgato.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_ICON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2021-11-13 11:48:00")
async def test_button_identify(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_elgato: MagicMock,
) -> None:
    """Test the Elgato identify button."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    state = hass.states.get("button.frenck_identify")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:help"
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("button.frenck_identify")
    assert entry
    assert entry.unique_id == "CN11A1A00001_identify"
    assert entry.entity_category == EntityCategory.CONFIG

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url is None
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }
    assert device_entry.entry_type is None
    assert device_entry.identifiers == {(DOMAIN, "CN11A1A00001")}
    assert device_entry.manufacturer == "Elgato"
    assert device_entry.model == "Elgato Key Light"
    assert device_entry.name == "Frenck"
    assert device_entry.sw_version == "1.0.3 (192)"
    assert device_entry.hw_version == "53"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.frenck_identify"},
        blocking=True,
    )

    assert len(mock_elgato.identify.mock_calls) == 1
    mock_elgato.identify.assert_called_with()

    state = hass.states.get("button.frenck_identify")
    assert state
    assert state.state == "2021-11-13T11:48:00+00:00"


async def test_button_identify_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_elgato: MagicMock,
) -> None:
    """Test an error occurs with the Elgato identify button."""
    mock_elgato.identify.side_effect = ElgatoError

    with pytest.raises(
        HomeAssistantError, match="An error occurred while identifying the Elgato Light"
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.frenck_identify"},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(mock_elgato.identify.mock_calls) == 1
