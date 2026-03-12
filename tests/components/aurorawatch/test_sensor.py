"""Test the AuroraWatch UK sensor platform."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from homeassistant.components.aurorawatch.const import (
    ATTR_API_VERSION,
    ATTR_LAST_UPDATED,
    ATTR_PROJECT_ID,
    ATTR_SITE_ID,
    ATTR_SITE_URL,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_aiohttp_session: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor setup."""
    await setup_integration(hass, mock_config_entry)

    entity_registry = er.async_get(hass)

    # Check that both sensors are created
    status_sensor = entity_registry.async_get("sensor.aurorawatch_uk_aurora_status")
    assert status_sensor
    assert status_sensor.unique_id == "aurorawatch_aurora_status"
    assert status_sensor.translation_key == "aurora_status"

    activity_sensor = entity_registry.async_get(
        "sensor.aurorawatch_uk_geomagnetic_activity"
    )
    assert activity_sensor
    assert activity_sensor.unique_id == "aurorawatch_geomagnetic_activity"
    assert activity_sensor.translation_key == "geomagnetic_activity"


async def test_sensor_states(
    hass: HomeAssistant,
    mock_aiohttp_session: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor states."""
    await setup_integration(hass, mock_config_entry)

    # Check status sensor state
    status_state = hass.states.get("sensor.aurorawatch_uk_aurora_status")
    assert status_state
    assert status_state.state == "green"

    # Check activity sensor state
    activity_state = hass.states.get("sensor.aurorawatch_uk_geomagnetic_activity")
    assert activity_state
    assert activity_state.state == "52.7"
    assert activity_state.attributes.get("unit_of_measurement") == "nT"
    assert activity_state.attributes.get("state_class") == "measurement"


async def test_sensor_attributes(
    hass: HomeAssistant,
    mock_aiohttp_session: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor attributes."""
    await setup_integration(hass, mock_config_entry)

    # Check status sensor attributes
    status_state = hass.states.get("sensor.aurorawatch_uk_aurora_status")
    assert status_state
    assert status_state.attributes.get(ATTR_LAST_UPDATED) == "2024-01-15T12:00:00Z"
    assert status_state.attributes.get(ATTR_PROJECT_ID) == "awn"
    assert status_state.attributes.get(ATTR_SITE_ID) == "lancaster"
    assert (
        status_state.attributes.get(ATTR_SITE_URL) == "http://aurorawatch.lancs.ac.uk"
    )
    assert status_state.attributes.get(ATTR_API_VERSION) == "0.2"
    assert (
        status_state.attributes.get("attribution") == "Data provided by AuroraWatch UK"
    )


async def test_sensor_update_failure_network_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor update with network error."""
    from unittest.mock import patch

    with patch(
        "homeassistant.components.aurorawatch.coordinator.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session

        # Mock network error
        mock_session.get.side_effect = ClientError("Connection failed")

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Sensors should be unavailable
        status_state = hass.states.get("sensor.aurorawatch_uk_aurora_status")
        assert status_state
        assert status_state.state == STATE_UNAVAILABLE

        activity_state = hass.states.get("sensor.aurorawatch_uk_geomagnetic_activity")
        assert activity_state
        assert activity_state.state == STATE_UNAVAILABLE


async def test_sensor_update_failure_invalid_xml(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor update with invalid XML."""
    from unittest.mock import patch

    from tests.components.aurorawatch.conftest import MOCK_MALFORMED_XML

    with patch(
        "homeassistant.components.aurorawatch.coordinator.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session

        # Mock malformed XML response
        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value=MOCK_MALFORMED_XML)
        mock_response.raise_for_status = AsyncMock()
        mock_session.get.return_value = mock_response

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Sensors should be unavailable due to parsing error
        status_state = hass.states.get("sensor.aurorawatch_uk_aurora_status")
        assert status_state
        assert status_state.state == STATE_UNAVAILABLE


async def test_sensor_update_failure_missing_fields(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor update with missing required fields."""
    from unittest.mock import patch

    from tests.components.aurorawatch.conftest import MOCK_INVALID_STATUS_XML

    with patch(
        "homeassistant.components.aurorawatch.coordinator.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session

        # Mock invalid XML response (missing required fields)
        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value=MOCK_INVALID_STATUS_XML)
        mock_response.raise_for_status = AsyncMock()
        mock_session.get.return_value = mock_response

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Sensors should be unavailable due to missing fields
        status_state = hass.states.get("sensor.aurorawatch_uk_aurora_status")
        assert status_state
        assert status_state.state == STATE_UNAVAILABLE


async def test_sensor_device_info(
    hass: HomeAssistant,
    mock_aiohttp_session: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor device info."""
    await setup_integration(hass, mock_config_entry)

    entity_registry = er.async_get(hass)
    status_sensor = entity_registry.async_get("sensor.aurorawatch_uk_aurora_status")
    assert status_sensor
    assert status_sensor.device_id

    from homeassistant.helpers import device_registry as dr

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(status_sensor.device_id)
    assert device
    assert device.manufacturer == "Lancaster University"
    assert device.model == "AuroraWatch UK"
    assert device.name == "AuroraWatch UK"
