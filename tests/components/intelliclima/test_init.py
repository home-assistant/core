"""Test the IntelliClima integration setup."""

from unittest.mock import AsyncMock

from pyintelliclima.api import IntelliClimaAPIError
from pyintelliclima.intelliclima_types import (
    IntelliClimaDevices,
    IntelliClimaFilterStatus,
)

from homeassistant.components.intelliclima.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_succeeds_when_filter_status_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test the config entry still loads when the filter-status endpoint fails.

    Filter status only backs a diagnostic binary sensor, so a transient
    failure of that ancillary endpoint must not block the fan, select, and
    sensor platforms from being set up.
    """
    mock_cloud_interface.get_filter_status.side_effect = IntelliClimaAPIError(
        "cannot compute filter status"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("fan.test_vmc") is not None

    state = hass.states.get("binary_sensor.test_vmc_filter_cleaning_required")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_filter_status_failure_isolated_per_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
    entity_registry: er.EntityRegistry,
    two_eco_devices: IntelliClimaDevices,
) -> None:
    """Test a filter-status failure for one device does not affect the others."""
    mock_cloud_interface.get_all_device_status.return_value = two_eco_devices
    working_device, failing_device = two_eco_devices.ecocomfort2_devices.values()
    filter_status = mock_cloud_interface.get_filter_status.return_value

    def _get_filter_status(serial: str) -> IntelliClimaFilterStatus:
        if serial == failing_device.crono_sn:
            raise IntelliClimaAPIError("cannot compute filter status")
        return filter_status

    mock_cloud_interface.get_filter_status.side_effect = _get_filter_status

    await setup_integration(hass, mock_config_entry)

    working_entity_id = entity_registry.async_get_entity_id(
        Platform.BINARY_SENSOR, DOMAIN, f"{working_device.id}_filter_cleaning"
    )
    assert working_entity_id is not None
    state = hass.states.get(working_entity_id)
    assert state is not None
    assert state.state == STATE_ON

    failing_entity_id = entity_registry.async_get_entity_id(
        Platform.BINARY_SENSOR, DOMAIN, f"{failing_device.id}_filter_cleaning"
    )
    assert failing_entity_id is not None
    state = hass.states.get(failing_entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
