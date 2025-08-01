"""Tests for the Freebox switches."""

from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TOGGLE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from .common import setup_platform
from .const import DATA_LAN_GET_PORT_FORWARDING_CONFIG_LIST


async def test_port_forwarding(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test port forwarding switch."""
    await setup_platform(hass, SWITCH_DOMAIN)

    registry = er.async_get(hass)
    entity_id = "switch.port_forwarding_1"

    entity = registry.async_get(entity_id)
    assert entity.disabled_by == "integration"

    # Simulate enabling the switch
    registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entity.config_entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"

    # Simulate toggling the switch
    with patch(
        "homeassistant.components.freebox.router.FreeboxRouter.port_forwarding"
    ) as mock_service:
        mock_service.edit_port_forwarding_configuration = AsyncMock()
        mock_service.edit_port_forwarding_configuration.assert_not_called()
        mock_service.get_all_port_forwarding_configuration = AsyncMock(
            return_value=DATA_LAN_GET_PORT_FORWARDING_CONFIG_LIST
        )
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            service_data={
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_service.edit_port_forwarding_configuration.assert_called_once_with(
            1, {"enabled": False}
        )
