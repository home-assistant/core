"""Test opentherm_gw buttons."""

from unittest.mock import AsyncMock, MagicMock

from pyotgw.vars import OTGW_MODE_RESET

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.opentherm_gw import DOMAIN as OPENTHERM_DOMAIN
from homeassistant.components.opentherm_gw.const import OpenThermDeviceIdentifier
from homeassistant.const import ATTR_ENTITY_ID, CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MINIMAL_STATUS

from tests.common import MockConfigEntry


async def test_restart_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test restart button."""

    mock_pyotgw.return_value.set_mode = AsyncMock(return_value=MINIMAL_STATUS)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        button_entity_id := entity_registry.async_get_entity_id(
            BUTTON_DOMAIN,
            OPENTHERM_DOMAIN,
            f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}-restart_button",
        )
    ) is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: button_entity_id,
        },
        blocking=True,
    )

    mock_pyotgw.return_value.set_mode.assert_awaited_once_with(OTGW_MODE_RESET)
