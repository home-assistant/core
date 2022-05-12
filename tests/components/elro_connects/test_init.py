"""Test the Elro Connects setup."""

import copy
from datetime import timedelta
from unittest.mock import AsyncMock

from elro.api import K1
import pytest

from homeassistant.components.elro_connects.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from .test_common import MOCK_DEVICE_STATUS_DATA

from tests.common import async_fire_time_changed


async def test_setup_integration_no_data(
    hass: HomeAssistant,
    mock_k1_connector: dict[AsyncMock],
    mock_entry: ConfigEntry,
) -> None:
    """Test we can setup an empty integration."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_setup_integration_update_fail(
    hass: HomeAssistant,
    caplog,
    mock_k1_connector: dict[AsyncMock],
    mock_entry: ConfigEntry,
) -> None:
    """Test if an update can fail with warnings."""
    mock_k1_connector["result"].side_effect = K1.K1ConnectionError
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert (
        "elro_connects integration not ready yet: K1 connection error; Retrying in background"
        in caplog.text
    )


async def test_setup_integration_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_k1_connector: dict[AsyncMock],
    mock_entry: ConfigEntry,
) -> None:
    """Test if an unknown backend error throws."""
    mock_k1_connector["result"].side_effect = Exception
    with pytest.raises(Exception):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert (
            "elro_connects integration not ready yet: K1 connection error; Retrying in background"
            in caplog.text
        )


async def test_setup_integration_with_data(
    hass: HomeAssistant,
    mock_k1_connector: dict[AsyncMock],
    mock_entry: ConfigEntry,
) -> None:
    """Test we can setup the integration with some data."""
    mock_k1_connector["result"].return_value = MOCK_DEVICE_STATUS_DATA
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_configure_platforms_dynamically(
    hass: HomeAssistant,
    mock_k1_connector: dict[AsyncMock],
    mock_entry: ConfigEntry,
) -> None:
    """Test we can setup and tear down platforms dynamically."""
    # Updated status holds device info for device [1,2,4]
    updated_status_data = copy.deepcopy(MOCK_DEVICE_STATUS_DATA)
    # Initial status holds device info for device [1,2]
    initial_status_data = copy.deepcopy(updated_status_data)
    initial_status_data.pop(4)

    # setup integration with 2 siren entities
    mock_k1_connector["result"].return_value = initial_status_data
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert hass.states.get("siren.beganegrond") is not None
    assert hass.states.get("siren.eerste_etage") is not None
    assert hass.states.get("siren.zolder") is None

    # Simulate a dynamic discovery update resulting in 3 siren entities
    mock_k1_connector["result"].return_value = updated_status_data
    time = dt.now() + timedelta(seconds=30)
    async_fire_time_changed(hass, time)
    # await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("siren.beganegrond") is not None
    assert hass.states.get("siren.eerste_etage") is not None
    assert hass.states.get("siren.zolder") is not None

    # Remove device 1 from api data, entity should appear offline with an unknown state
    updated_status_data.pop(1)

    mock_k1_connector["result"].return_value = updated_status_data
    time = time + timedelta(seconds=30)
    async_fire_time_changed(hass, time)
    await hass.async_block_till_done()

    assert hass.states.get("siren.beganegrond").state == "unknown"
    assert hass.states.get("siren.eerste_etage") is not None
    assert hass.states.get("siren.zolder") is not None
