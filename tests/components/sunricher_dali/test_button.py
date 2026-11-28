"""Test the Sunricher DALI button platform."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the button entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_identify_button_press(
    hass: HomeAssistant,
    mock_devices: list[MagicMock],
) -> None:
    """Test pressing the identify button calls device.identify()."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: "button.dimmer_0000_02"},
        blocking=True,
    )

    mock_devices[0].identify.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_identify_button_press_gateway_disconnected(
    hass: HomeAssistant,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
) -> None:
    """Test pressing the identify button raises when the gateway is disconnected."""
    mock_gateway.is_connected = False

    with pytest.raises(HomeAssistantError, match="The DALI gateway is not connected"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {CommonServiceArgument.ENTITY_ID: "button.dimmer_0000_02"},
            blocking=True,
        )

    mock_devices[0].identify.assert_not_called()
