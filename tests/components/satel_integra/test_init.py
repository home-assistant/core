"""Test init of Satel Integra integration."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from satel_integra import (
    SatelConnectFailedError,
    SatelConnectionInitializationError,
    SatelMonitoringStartError,
    SatelPanelBusyError,
    SatelUnexpectedResponseError,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_PANEL_DOMAIN
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.satel_integra.config_flow import SatelConfigFlow
from homeassistant.components.satel_integra.const import (
    CONF_ENABLE_TEMPERATURE_SENSOR,
    CONF_ENCRYPTION_KEY,
    CONF_OUTPUT_NUMBER,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    MOCK_CONFIG_DATA,
    MOCK_CONFIG_OPTIONS,
    MOCK_ENTRY_ID,
    MOCK_OUTPUT_SUBENTRY,
    MOCK_PARTITION_SUBENTRY,
    MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
    MOCK_ZONE_SUBENTRY,
    get_alarm_status_callback,
    setup_integration,
)


@pytest.mark.parametrize(
    ("original", "number_property"),
    [
        (MOCK_PARTITION_SUBENTRY, CONF_PARTITION_NUMBER),
        (MOCK_ZONE_SUBENTRY, CONF_ZONE_NUMBER),
        (MOCK_OUTPUT_SUBENTRY, CONF_OUTPUT_NUMBER),
        (MOCK_SWITCHABLE_OUTPUT_SUBENTRY, CONF_SWITCHABLE_OUTPUT_NUMBER),
    ],
)
async def test_config_flow_migration_v1_1_to_v1_2(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    original: ConfigSubentry,
    number_property: str,
) -> None:
    """Test that the configured number is added to the subentry title."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
        entry_id=MOCK_ENTRY_ID,
        version=1,
        minor_version=1,
    )
    config_entry.subentries = deepcopy({original.subentry_id: original})

    await setup_integration(hass, config_entry)

    assert config_entry.version == SatelConfigFlow.VERSION
    assert config_entry.minor_version == SatelConfigFlow.MINOR_VERSION

    subentry = config_entry.subentries.get(original.subentry_id)
    assert subentry is not None
    assert subentry.title == f"{original.title} ({original.data[number_property]})"


@pytest.mark.parametrize(
    ("platform", "old_id", "new_id"),
    [
        (ALARM_PANEL_DOMAIN, "satel_alarm_panel_1", f"{MOCK_ENTRY_ID}_alarm_panel_1"),
        (BINARY_SENSOR_DOMAIN, "satel_zone_1", f"{MOCK_ENTRY_ID}_zone_1"),
        (BINARY_SENSOR_DOMAIN, "satel_output_1", f"{MOCK_ENTRY_ID}_output_1"),
        (SWITCH_DOMAIN, "satel_switch_1", f"{MOCK_ENTRY_ID}_switch_1"),
    ],
)
async def test_config_flow_migration_v1_to_v2(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    entity_registry: EntityRegistry,
    platform: str,
    old_id: str,
    new_id: str,
) -> None:
    """Test that the unique ID is migrated to use the config entry id."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
        entry_id=MOCK_ENTRY_ID,
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        platform,
        DOMAIN,
        old_id,
        config_entry=config_entry,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get(entity.entity_id)

    assert entity is not None
    assert entity.unique_id == new_id

    assert config_entry.version == SatelConfigFlow.VERSION
    assert config_entry.minor_version == SatelConfigFlow.MINOR_VERSION


async def test_config_flow_migration_v2_1_to_v2_2(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
) -> None:
    """Test that the encryption key is added to the config entry."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data={CONF_HOST: "192.168.0.2", CONF_PORT: 7094},
        options=MOCK_CONFIG_OPTIONS,
        entry_id=MOCK_ENTRY_ID,
        version=2,
        minor_version=1,
    )
    await setup_integration(hass, config_entry)

    assert config_entry.version == SatelConfigFlow.VERSION
    assert config_entry.minor_version == SatelConfigFlow.MINOR_VERSION

    assert config_entry.data == {
        CONF_HOST: "192.168.0.2",
        CONF_PORT: 7094,
        CONF_ENCRYPTION_KEY: None,
    }


async def test_config_flow_migration_v2_2_to_v2_3(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
) -> None:
    """Test that the temperature sensor option is added to zone subentries."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
        entry_id=MOCK_ENTRY_ID,
        version=2,
        minor_version=2,
    )

    config_entry.subentries = deepcopy(
        {
            MOCK_ZONE_SUBENTRY.subentry_id: ConfigSubentry(
                subentry_type=MOCK_ZONE_SUBENTRY.subentry_type,
                subentry_id=MOCK_ZONE_SUBENTRY.subentry_id,
                unique_id=MOCK_ZONE_SUBENTRY.unique_id,
                title=MOCK_ZONE_SUBENTRY.title,
                data={
                    CONF_NAME: "Zone",
                    CONF_ZONE_TYPE: BinarySensorDeviceClass.MOTION,
                    CONF_ZONE_NUMBER: 1,
                },
            )
        }
    )

    await setup_integration(hass, config_entry)

    assert config_entry.version == SatelConfigFlow.VERSION
    assert config_entry.minor_version == SatelConfigFlow.MINOR_VERSION

    subentry = config_entry.subentries.get(MOCK_ZONE_SUBENTRY.subentry_id)
    assert subentry is not None
    assert subentry.data[CONF_ENABLE_TEMPERATURE_SENSOR] is False
    assert subentry.data[CONF_NAME] == "Zone"
    assert subentry.data[CONF_ZONE_TYPE] == BinarySensorDeviceClass.MOTION
    assert subentry.data[CONF_ZONE_NUMBER] == 1


async def test_parent_device_exists(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_satel: AsyncMock,
    device_registry: DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a parent device is created for the alarm panel."""

    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_ENTRY_ID), mock_config_entry.entry_id
    )
    assert device_entry == snapshot(name="parent-device")
    mock_satel.read_panel_info.assert_awaited_once_with()


async def test_panel_info_read_error(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    device_registry: DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a panel information read error does not prevent setup."""
    mock_satel.read_panel_info.side_effect = SatelUnexpectedResponseError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_ENTRY_ID), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.model is None
    assert device_entry.sw_version is None


async def test_unload_unsubscribes_connection_status_callbacks(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test connection status callbacks are unsubscribed on unload."""
    # 5 coordinators + 1 client = 6 callbacks to unsubscribe
    unsubscribe_callbacks = [MagicMock(return_value=None) for _ in range(6)]
    mock_satel.add_connection_status_callback.side_effect = unsubscribe_callbacks

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    for unsubscribe_callback in unsubscribe_callbacks:
        unsubscribe_callback.assert_called_once_with()
    mock_satel.close.assert_awaited_once_with()


async def test_unload_cancels_pending_partition_update(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unload cancels a pending partition state update."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator_partitions

    with patch.object(coordinator, "async_set_updated_data") as set_updated_data:
        get_alarm_status_callback(mock_satel)()

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        freezer.tick(1)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    set_updated_data.assert_not_called()


async def test_setup_failure_unsubscribes_connection_status_callbacks(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a setup failure unsubscribes connection status callbacks."""
    unsubscribe_callbacks = [MagicMock(return_value=None) for _ in range(6)]
    mock_satel.add_connection_status_callback.side_effect = unsubscribe_callbacks
    mock_satel.read_panel_info.side_effect = RuntimeError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    for unsubscribe_callback in unsubscribe_callbacks:
        unsubscribe_callback.assert_called_once_with()


async def test_unload_unsubscribes_monitor_callbacks(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test monitor callbacks are unsubscribed on unload."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for callback_method in (
        mock_satel.add_alarm_status_callback,
        mock_satel.add_zone_changed_callback,
        mock_satel.add_output_changed_callback,
    ):
        callback_method.return_value.assert_called_once_with()


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (SatelConnectFailedError, ConfigEntryState.SETUP_RETRY),
        (SatelPanelBusyError, ConfigEntryState.SETUP_RETRY),
        (SatelConnectionInitializationError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the client async_connect."""
    mock_satel.connect.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state


async def test_monitoring_start_error(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when monitoring fails to start."""
    mock_satel.start.side_effect = SatelMonitoringStartError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == (
        "Connected to the alarm panel, but the panel did not confirm the request to start sending status updates"
    )
    mock_satel.start.assert_awaited_once_with(enable_monitoring=True)
    mock_satel.read_panel_info.assert_not_awaited()


async def test_connection_state_logging(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logging an outage and subsequent recovery."""
    await setup_integration(hass, mock_config_entry)

    assert mock_satel.add_connection_status_callback.called
    connection_status_callback = (
        mock_satel.add_connection_status_callback.call_args.args[0]
    )

    mock_satel.connected = False
    connection_status_callback()

    assert "Satel Integra device is unavailable" in caplog.text

    caplog.clear()
    mock_satel.connected = True
    connection_status_callback()

    assert "Satel Integra device is back online" in caplog.text
