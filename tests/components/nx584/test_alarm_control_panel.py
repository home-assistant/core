"""Tests for the NX584 alarm control panel."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.nx584.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import TEST_HOST, TEST_PORT

from tests.common import MockConfigEntry

ENTITY_ID = "alarm_control_panel.nx584"


@pytest.mark.usefixtures("mock_client", "mock_watcher")
async def test_entity_id_from_entry_name(hass: HomeAssistant) -> None:
    """Test the alarm panel takes the imported YAML name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT, CONF_NAME: "House"},
        unique_id=f"{TEST_HOST}:{TEST_PORT}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.house")
    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.usefixtures("mock_watcher")
@pytest.mark.parametrize(
    ("service", "bypass"),
    [
        pytest.param("bypass_zone", True, id="bypass"),
        pytest.param("unbypass_zone", False, id="unbypass"),
    ],
)
async def test_bypass_services(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    bypass: bool,
) -> None:
    """Test the bypass services call the client."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID, "zone": 2}, blocking=True
    )

    mock_client.return_value.set_bypass.assert_called_once_with(2, bypass)
