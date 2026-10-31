"""Tests for the NX584 alarm control panel."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
import requests

from homeassistant.components.nx584.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import TEST_HOST, TEST_PORT

ENTITY_ID = "alarm_control_panel.nx584"


@pytest.mark.usefixtures("mock_client", "mock_watcher")
async def test_name_from_entry_title(hass: HomeAssistant) -> None:
    """Test the alarm panel is named after the entry title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="House",
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.house")
    assert state
    assert state.name == "House"
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


@pytest.mark.usefixtures("mock_watcher")
@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        pytest.param(requests.exceptions.ConnectionError, None, id="cannot_connect"),
        pytest.param(requests.exceptions.ReadTimeout, None, id="timeout"),
        pytest.param(None, [], id="no_partitions"),
    ],
)
async def test_update_partitions_unavailable(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: type[Exception] | None,
    return_value: list[dict[str, object]] | None,
) -> None:
    """Test the panel is unavailable while partitions cannot be listed."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    partitions = mock_client.return_value.list_partitions
    working_partitions = partitions.return_value
    partitions.side_effect = side_effect
    partitions.return_value = return_value
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    partitions.side_effect = None
    partitions.return_value = working_partitions
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == "disarmed"
