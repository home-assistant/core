"""Tests for the Alexa Devices number platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from aioamazondevices.exceptions import CannotSetFeature
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import assert_device_removed_and_readded, setup_integration
from .const import TEST_DEVICE_THERMOSTAT, TEST_DEVICE_THERMOSTAT_SN

ACTIVE_ENTITY_ID = "number.thermostat_test_active_brightness"
INACTIVE_ENTITY_ID = "number.thermostat_test_inactive_brightness"
ACTIVE_SENSOR_KEY = "amz_them_active_brightness"


@pytest.fixture
def mock_thermostat(mock_amazon_devices_client: AsyncMock) -> AsyncMock:
    """Return a client that only reports the thermostat."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_THERMOSTAT_SN: deepcopy(TEST_DEVICE_THERMOSTAT)
    }
    return mock_amazon_devices_client


@pytest.mark.usefixtures("mock_thermostat", "entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "instance", "value", "expected"),
    [
        pytest.param(ACTIVE_ENTITY_ID, "2", 2, 2, id="active"),
        pytest.param(INACTIVE_ENTITY_ID, "3", 5, 5, id="inactive"),
        pytest.param(ACTIVE_ENTITY_ID, "2", 3.6, 4, id="not_whole_number"),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_thermostat: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    instance: str,
    value: float,
    expected: int,
) -> None:
    """Test setting a value sends a whole number and updates state optimistically."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    mock_thermostat.call_feature_operation.assert_called_once_with(
        mock_thermostat.get_devices_data.return_value[TEST_DEVICE_THERMOSTAT_SN],
        "range",
        "setRangeValue",
        command_payload={"rangeValue": expected},
        instance=instance,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == str(expected)


async def test_set_value_cannot_set_feature(
    hass: HomeAssistant,
    mock_thermostat: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a rejected command raises and keeps the current state."""
    mock_thermostat.call_feature_operation.side_effect = CannotSetFeature
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ACTIVE_ENTITY_ID, ATTR_VALUE: 2},
            blocking=True,
        )

    assert exc_info.value.translation_key == "cannot_set_feature_with_error"
    assert (state := hass.states.get(ACTIVE_ENTITY_ID))
    assert state.state == "4"


async def test_unavailable_on_sensor_error(
    hass: HomeAssistant,
    mock_thermostat: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the number is unavailable when its sensor reports an error."""
    mock_thermostat.sensors[TEST_DEVICE_THERMOSTAT_SN][ACTIVE_SENSOR_KEY].error = True
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ACTIVE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_unknown_without_value(
    hass: HomeAssistant,
    mock_thermostat: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the number is unknown when its sensor has no value."""
    mock_thermostat.sensors[TEST_DEVICE_THERMOSTAT_SN][ACTIVE_SENSOR_KEY].value = None
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ACTIVE_ENTITY_ID))
    assert state.state == STATE_UNKNOWN


async def test_created_without_sensor_value(
    hass: HomeAssistant,
    mock_thermostat: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the number is created from the feature before a value arrives."""
    del mock_thermostat.sensors[TEST_DEVICE_THERMOSTAT_SN][ACTIVE_SENSOR_KEY]
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ACTIVE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_not_created_without_feature(
    hass: HomeAssistant,
    mock_thermostat: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the numbers are not created when the feature is unsupported."""
    mock_thermostat.get_devices_data.return_value[
        TEST_DEVICE_THERMOSTAT_SN
    ].features = {}
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ACTIVE_ENTITY_ID) is None
    assert hass.states.get(INACTIVE_ENTITY_ID) is None


async def test_device_removed_and_readded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_thermostat: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities are recreated when a device is removed and re-added."""
    await assert_device_removed_and_readded(
        hass,
        freezer,
        mock_thermostat,
        mock_config_entry,
        entity_id=ACTIVE_ENTITY_ID,
        devices_with={TEST_DEVICE_THERMOSTAT_SN: TEST_DEVICE_THERMOSTAT},
        devices_without={},
    )
