"""Test the SMA switch platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pysma import (
    ModbusControl,
    SmaConnectionException,
    SmaTimeoutException,
    SmaWriteException,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sma.const import DEFAULT_SCAN_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import OPERATING_STATUS_OFF_TAG, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SWITCH_ENTITY_ID = "switch.sma_device_name_inverter_enabled"


@pytest.fixture(autouse=True)
def _mock_inverter_enabled_supported(mock_sma_modbus: MagicMock) -> None:
    """Expose the inverter_enabled control as supported by default."""
    mock_sma_modbus.get_control_schema.return_value = (0, 1)
    mock_sma_modbus.get_control.return_value = 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_sma_client: Generator,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all switch entities."""
    with patch(
        "homeassistant.components.sma.PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_not_supported(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch is not created when the control is not supported."""
    mock_sma_modbus.get_control_schema.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SWITCH_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("service_call", "control_value", "operating_status_raw_value", "state"),
    [
        (SERVICE_TURN_ON, 1, 569, STATE_ON),  # 569 == Activated
        (SERVICE_TURN_OFF, 0, OPERATING_STATUS_OFF_TAG, STATE_OFF),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
    service_call: str,
    control_value: int,
    operating_status_raw_value: int,
    state: str,
) -> None:
    """Test turning the switch on and off."""
    await setup_integration(hass, mock_config_entry)
    mock_sma_client.get_sensors.return_value[
        "operating_status_general"
    ].raw_value = operating_status_raw_value

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service_call,
        {"entity_id": SWITCH_ENTITY_ID},
        blocking=True,
    )

    mock_sma_modbus.set_control.assert_called_once_with(
        ModbusControl.INVERTER_ENABLED, control_value
    )
    assert hass.states.get(SWITCH_ENTITY_ID).state == state


@pytest.mark.parametrize("service_call", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.parametrize(
    ("raise_exception", "expected_exception"),
    [
        (SmaConnectionException, HomeAssistantError),
        (SmaTimeoutException, HomeAssistantError),
        (SmaWriteException, HomeAssistantError),
    ],
)
async def test_turn_on_off_exceptions(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
    service_call: str,
    raise_exception: type[Exception],
    expected_exception: type[Exception],
) -> None:
    """Test switch actions raise a HomeAssistantError on Modbus errors."""
    await setup_integration(hass, mock_config_entry)

    mock_sma_modbus.set_control.side_effect = raise_exception("boom")
    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service_call,
            {"entity_id": SWITCH_ENTITY_ID},
            blocking=True,
        )


async def test_switch_added_after_delayed_discovery(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch is added once Modbus discovery later succeeds."""
    mock_sma_modbus.get_control_schema.return_value = None
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(SWITCH_ENTITY_ID) is None

    mock_sma_modbus.get_control_schema.return_value = (0, 1)
    coordinator = mock_config_entry.runtime_data
    await coordinator._async_discover_modbus()
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_ENTITY_ID) is not None


async def test_unavailable_when_control_unreadable(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the switch is unavailable when the control cannot be read."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON

    mock_sma_modbus.get_control.side_effect = SmaConnectionException("boom")
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_UNAVAILABLE
