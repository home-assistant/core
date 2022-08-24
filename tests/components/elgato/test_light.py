"""Tests for the Elgato Key Light light platform."""
from unittest.mock import MagicMock

from elgato import ElgatoError
import pytest

from homeassistant.components.elgato.const import DOMAIN, SERVICE_IDENTIFY
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_light_state_temperature(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_elgato: MagicMock,
) -> None:
    """Test the creation and values of the Elgato Lights in temperature mode."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # First segment of the strip
    state = hass.states.get("light.frenck")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 54
    assert state.attributes.get(ATTR_COLOR_TEMP) == 297
    assert state.attributes.get(ATTR_HS_COLOR) == (27.316, 47.743)
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.COLOR_TEMP
    assert state.attributes.get(ATTR_MIN_MIREDS) == 143
    assert state.attributes.get(ATTR_MAX_MIREDS) == 344
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [ColorMode.COLOR_TEMP]
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.frenck")
    assert entry
    assert entry.unique_id == "CN11A1A00001"

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


@pytest.mark.parametrize(
    "mock_elgato", [{"settings": "color", "state": "color"}], indirect=True
)
async def test_light_state_color(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_elgato: MagicMock,
) -> None:
    """Test the creation and values of the Elgato Lights in temperature mode."""
    entity_registry = er.async_get(hass)

    # First segment of the strip
    state = hass.states.get("light.frenck")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128
    assert state.attributes.get(ATTR_COLOR_TEMP) is None
    assert state.attributes.get(ATTR_HS_COLOR) == (358.0, 6.0)
    assert state.attributes.get(ATTR_MIN_MIREDS) == 153
    assert state.attributes.get(ATTR_MAX_MIREDS) == 285
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.HS
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.frenck")
    assert entry
    assert entry.unique_id == "CN11A1A00001"


@pytest.mark.parametrize(
    "mock_elgato", [{"settings": "color", "state": "temperature"}], indirect=True
)
async def test_light_change_state_temperature(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_elgato: MagicMock,
) -> None:
    """Test the change of state of a Elgato Key Light device."""
    state = hass.states.get("light.frenck")
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.frenck",
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_TEMP: 100,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(mock_elgato.light.mock_calls) == 1
    mock_elgato.light.assert_called_with(
        on=True, brightness=100, temperature=100, hue=None, saturation=None
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.frenck",
            ATTR_BRIGHTNESS: 255,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(mock_elgato.light.mock_calls) == 2
    mock_elgato.light.assert_called_with(
        on=True, brightness=100, temperature=297, hue=None, saturation=None
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.frenck"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(mock_elgato.light.mock_calls) == 3
    mock_elgato.light.assert_called_with(on=False)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.frenck",
            ATTR_BRIGHTNESS: 255,
            ATTR_HS_COLOR: (10.1, 20.2),
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(mock_elgato.light.mock_calls) == 4
    mock_elgato.light.assert_called_with(
        on=True, brightness=100, temperature=None, hue=10.1, saturation=20.2
    )


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_light_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_elgato: MagicMock,
    service: str,
) -> None:
    """Test error/unavailable handling of an Elgato Light."""
    mock_elgato.state.side_effect = ElgatoError
    mock_elgato.light.side_effect = ElgatoError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "light.frenck"},
            blocking=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("light.frenck")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_light_identify(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_elgato: MagicMock,
) -> None:
    """Test identifying an Elgato Light."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_IDENTIFY,
        {
            ATTR_ENTITY_ID: "light.frenck",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(mock_elgato.identify.mock_calls) == 1
    mock_elgato.identify.assert_called_with()


async def test_light_identify_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_elgato: MagicMock,
) -> None:
    """Test error occurred during identifying an Elgato Light."""
    mock_elgato.identify.side_effect = ElgatoError
    with pytest.raises(
        HomeAssistantError, match="An error occurred while identifying the Elgato Light"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_IDENTIFY,
            {
                ATTR_ENTITY_ID: "light.frenck",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(mock_elgato.identify.mock_calls) == 1
