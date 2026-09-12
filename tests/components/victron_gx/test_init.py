"""Test the victron_gx init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from victron_mqtt import (
    AuthenticationError,
    CannotConnectError,
    Hub as VictronVenusHub,
    MetricKind,
)
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.components.victron_gx import async_remove_config_entry_device
from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry

LEGACY_SENSOR_UNIQUE_ID = (
    f"{MOCK_INSTALLATION_ID}_evcharger_0_evcharger_max_set_current"
)
LEGACY_SENSOR_ENTITY_ID = "sensor.ev_charging_station_maximum_set_current"
DEPRECATED_SENSOR_ISSUE_ID = f"deprecated_sensor_{LEGACY_SENSOR_UNIQUE_ID}"


def _register_legacy_sensor(
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    *,
    disabled: bool = False,
) -> None:
    """Register a legacy EV charger sensor."""
    entry = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        LEGACY_SENSOR_UNIQUE_ID,
        suggested_object_id="ev_charging_station_maximum_set_current",
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.USER if disabled else None,
    )
    assert entry.entity_id == LEGACY_SENSOR_ENTITY_ID


@pytest.fixture
def mock_victron_hub_library():
    """Mock the victron_mqtt library."""
    with patch("homeassistant.components.victron_gx.hub.VictronVenusHub") as mock_lib:
        hub_instance = MagicMock()
        hub_instance.connect = AsyncMock()
        hub_instance.disconnect = AsyncMock()
        hub_instance.installation_id = MOCK_INSTALLATION_ID
        mock_lib.return_value = hub_instance
        yield mock_lib


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_legacy_evcharger_sensor_creates_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an enabled legacy sensor remains and creates a repair."""
    mock_config_entry.add_to_hass(hass)
    _register_legacy_sensor(entity_registry, mock_config_entry)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(LEGACY_SENSOR_ENTITY_ID) is not None
    assert hass.states.get(LEGACY_SENSOR_ENTITY_ID) is None
    issue = issue_registry.async_get_issue(DOMAIN, DEPRECATED_SENSOR_ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "deprecated_sensor"
    assert issue.translation_placeholders == {"entity_id": LEGACY_SENSOR_ENTITY_ID}


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_legacy_evcharger_sensor_repair_lists_uses(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair lists automations and scripts using the legacy sensor."""
    mock_config_entry.add_to_hass(hass)
    _register_legacy_sensor(entity_registry, mock_config_entry)
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: {
                "alias": "Test automation",
                "trigger": {
                    "platform": "state",
                    "entity_id": LEGACY_SENSOR_ENTITY_ID,
                },
                "action": [],
            }
        },
    )
    assert await async_setup_component(
        hass,
        SCRIPT_DOMAIN,
        {
            SCRIPT_DOMAIN: {
                "test_script": {
                    "sequence": {
                        "action": "homeassistant.turn_on",
                        "target": {"entity_id": LEGACY_SENSOR_ENTITY_ID},
                    }
                }
            }
        },
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(LEGACY_SENSOR_ENTITY_ID) is not None
    issue = issue_registry.async_get_issue(DOMAIN, DEPRECATED_SENSOR_ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "deprecated_sensor_in_use"
    placeholders = issue.translation_placeholders
    assert placeholders is not None
    assert "automation.test_automation" in placeholders["items"]
    assert "/config/script/edit/test_script" in placeholders["items"]


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_disabled_legacy_evcharger_sensor_is_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a disabled legacy sensor and its repair are removed."""
    mock_config_entry.add_to_hass(hass)
    _register_legacy_sensor(entity_registry, mock_config_entry, disabled=True)
    ir.async_create_issue(
        hass,
        DOMAIN,
        DEPRECATED_SENSOR_ISSUE_ID,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_sensor",
        translation_placeholders={
            "entity_id": LEGACY_SENSOR_ENTITY_ID,
        },
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(LEGACY_SENSOR_ENTITY_ID) is None
    assert hass.states.get(LEGACY_SENSOR_ENTITY_ID) is None
    assert issue_registry.async_get_issue(DOMAIN, DEPRECATED_SENSOR_ISSUE_ID) is None


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unload entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_unload_entry_does_not_cleanup_on_platform_unload_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unload failure does not stop hub or clear callbacks."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_config_entry.runtime_data.new_metric_callbacks[MetricKind.SENSOR] = MagicMock()
    hub_disconnect = mock_config_entry.runtime_data._hub.disconnect

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    hub_disconnect.assert_not_awaited()


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_stop_on_homeassistant_stop(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test hub stops when Home Assistant stops."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    hub_disconnect = mock_config_entry.runtime_data._hub.disconnect
    hub_disconnect.assert_not_awaited()

    # Fire the stop event
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    hub_disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("connect_exception", "expected_state"),
    [
        (CannotConnectError("Connection failed"), ConfigEntryState.SETUP_RETRY),
        (AuthenticationError("Auth failed"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_entry_start_failure_unloads_platforms_and_callbacks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_victron_hub_library: MagicMock,
    connect_exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup cleanup when hub start fails after platform forwarding."""
    mock_config_entry.add_to_hass(hass)
    mock_victron_hub_library.return_value.connect.side_effect = connect_exception

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    assert mock_config_entry.runtime_data.new_metric_callbacks == {}


async def test_hub_start_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_victron_hub_library: MagicMock,
) -> None:
    """Test hub start with connection error."""
    mock_config_entry.add_to_hass(hass)

    mock_victron_hub_library.return_value.connect.side_effect = CannotConnectError(
        "Connection failed"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_hub_start_success(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
) -> None:
    """Test successful hub start."""
    victron_hub, mock_config_entry = init_integration

    # Verify the hub was started (integration was set up successfully)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert victron_hub.installation_id == MOCK_INSTALLATION_ID


async def test_device_via_device_links(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a child device links to its missing parent via via_device_id."""
    victron_hub, mock_config_entry = init_integration

    # Inject only a battery metric. Its parent (system_0) has no metric of its
    # own here, so it is not registered on its own; the child must trigger
    # registration of the missing parent to be able to link to it.
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Dc/0/Current",
        '{"value": 10.5}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    system_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_INSTALLATION_ID}_system_0"), mock_config_entry.entry_id
    )
    assert system_device is not None
    # The GX gateway has no parent — it IS the root.
    assert system_device.via_device_id is None

    battery_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_INSTALLATION_ID}_battery_0"), mock_config_entry.entry_id
    )
    assert battery_device is not None
    # Battery is a child of the GX gateway, not an orphan.
    assert battery_device.via_device_id == system_device.id


async def test_hub_start_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_victron_hub_library: MagicMock,
) -> None:
    """Test hub start with authentication error."""
    mock_config_entry.add_to_hass(hass)

    mock_victron_hub_library.return_value.connect.side_effect = AuthenticationError(
        "Authentication failed"
    )

    # Attempt to set up the config entry - should fail with auth error
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry is in SETUP_ERROR state (auth failed)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_hub_stop(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
) -> None:
    """Test hub stop."""
    _, mock_config_entry = init_integration

    # Verify it's initially loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Unload the config entry (which stops the hub)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify hub is disconnected by checking config entry state
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_hub_stop_disconnect_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_victron_hub_library: MagicMock,
) -> None:
    """Test hub stop gracefully handles disconnect errors."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Make disconnect raise an error
    mock_victron_hub_library.return_value.disconnect.side_effect = Exception(
        "disconnect failed"
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a device from the config entry."""
    victron_hub, mock_config_entry = init_integration

    # A device that was never discovered should be removable
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_test_device")},
    )

    result = await async_remove_config_entry_device(
        hass, mock_config_entry, device_entry
    )
    assert result is True

    # Inject a sensor to make battery_0 a known device
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Dc/0/Current",
        '{"value": 10.5}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    # A device that is currently connected should NOT be removable
    connected_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_battery_0")},
    )

    result = await async_remove_config_entry_device(
        hass, mock_config_entry, connected_device
    )
    assert result is False
