"""Test Flow-it binary sensor platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

BYPASS_ENTITY_ID = "binary_sensor.001122334455_bypass_active"
CONDENSATION_ENTITY_ID = "binary_sensor.001122334455_condensation_alert"
ICE_ENTITY_ID = "binary_sensor.001122334455_ice_alert"
REBOOT_PENDING_ENTITY_ID = "binary_sensor.001122334455_reboot_pending"
SERVICE_ENTITY_ID = "binary_sensor.001122334455_service_required"
WARMUP_ENTITY_ID = "binary_sensor.001122334455_warmup_mode"
WORRIES_ENTITY_ID = "binary_sensor.001122334455_general_issue"


@pytest.fixture(autouse=True)
def binary_sensor_only() -> Generator[None]:
    """Only setup binary sensor platform."""
    with patch("homeassistant.components.flow_it.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_setup(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor platform setup and entity registry."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensor_warmup_disabled_by_default(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test warmup binary sensor is disabled by default."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(WARMUP_ENTITY_ID)
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(WARMUP_ENTITY_ID) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_none_values(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor state when values are None."""
    mock_flow_it.return_value.state.data.alert.ice = None
    mock_flow_it.return_value.state.data.alert.condensation = None
    mock_flow_it.return_value.state.data.alert.service = None
    mock_flow_it.return_value.state.data.alert.worries = None
    mock_flow_it.return_value.state.data.alert.update_reboot = None
    mock_flow_it.return_value.state.data.alert.warmup = None
    mock_flow_it.return_value.state.data.mode.bypassOn = None

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in (
        ICE_ENTITY_ID,
        CONDENSATION_ENTITY_ID,
        SERVICE_ENTITY_ID,
        WORRIES_ENTITY_ID,
        REBOOT_PENDING_ENTITY_ID,
        BYPASS_ENTITY_ID,
        WARMUP_ENTITY_ID,
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "field", "is_mode"),
    [
        pytest.param(BYPASS_ENTITY_ID, "bypassOn", True, id="bypass_on"),
        pytest.param(CONDENSATION_ENTITY_ID, "condensation", False, id="condensation"),
        pytest.param(ICE_ENTITY_ID, "ice", False, id="ice"),
        pytest.param(
            REBOOT_PENDING_ENTITY_ID, "update_reboot", False, id="update_reboot"
        ),
        pytest.param(SERVICE_ENTITY_ID, "service", False, id="service"),
        pytest.param(WARMUP_ENTITY_ID, "warmup", False, id="warmup"),
        pytest.param(WORRIES_ENTITY_ID, "worries", False, id="worries"),
    ],
)
async def test_binary_sensor_update(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    field: str,
    is_mode: bool,
) -> None:
    """Test binary sensor state updates via periodic coordinator refresh."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    target = (
        mock_flow_it.return_value.state.data.mode
        if is_mode
        else mock_flow_it.return_value.state.data.alert
    )
    setattr(target, field, True)

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
