"""Tests for the Elgato Key Light light platform."""

from unittest.mock import MagicMock

from elgato import ElgatoError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.elgato.const import DOMAIN, SERVICE_IDENTIFY
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
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

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.usefixtures("mock_elgato")
@pytest.mark.parametrize(
    ("device_fixtures", "state_variant"),
    [
        ("key-light", "state"),
        ("light-strip", "state"),
        ("light-strip", "state-color-temperature"),
    ],
)
async def test_light_state_temperature(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and values of the Elgato Lights in temperature mode."""

    # First segment of the strip
    assert (state := hass.states.get("light.frenck"))
    assert state == snapshot

    assert (entry := entity_registry.async_get("light.frenck"))
    assert entry == snapshot

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("device_fixtures", "state_variant"), [("light-strip", "state-color-temperature")]
)
@pytest.mark.usefixtures("state_variant", "device_fixtures", "init_integration")
async def test_light_change_state_temperature(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
) -> None:
    """Test the change of state of a Elgato Key Light device."""
    assert (state := hass.states.get("light.frenck"))
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
    assert len(mock_elgato.light.mock_calls) == 4
    mock_elgato.light.assert_called_with(
        on=True, brightness=100, temperature=None, hue=10.1, saturation=20.2
    )


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_light_unavailable(
    hass: HomeAssistant, mock_elgato: MagicMock, service: str
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

    assert (state := hass.states.get("light.frenck"))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_light_identify(hass: HomeAssistant, mock_elgato: MagicMock) -> None:
    """Test identifying an Elgato Light."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_IDENTIFY,
        {
            ATTR_ENTITY_ID: "light.frenck",
        },
        blocking=True,
    )
    assert len(mock_elgato.identify.mock_calls) == 1
    mock_elgato.identify.assert_called_with()

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

    assert len(mock_elgato.identify.mock_calls) == 2
