"""Test setting up and unloading PrusaLink."""

from datetime import timedelta
from unittest.mock import patch

from httpx import ConnectError
from pyprusalink.types import InvalidAuth, PrusaLinkError
import pytest

from homeassistant.components.prusalink import DOMAIN
from homeassistant.components.prusalink.config_flow import PrusaLinkConfigFlow
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("mock_api")


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test device info is populated with serial and firmware."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "serial-1337")})
    assert device is not None
    assert device.serial_number == "serial-1337"
    assert device.sw_version == "6.1.2+11023"

    # `location` from /api/v1/info is set as suggested_area; the device gets
    # placed in that area (created on the fly when not pre-existing).
    assert device.area_id is not None
    area = area_registry.async_get_area(device.area_id)
    assert area is not None
    assert area.name == "Workshop"


async def test_backfills_unique_id_for_existing_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration backfills config entry unique_id from printer serial."""
    assert mock_config_entry.unique_id is None
    assert mock_config_entry.minor_version == 2

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.unique_id == "serial-1337"
    assert mock_config_entry.minor_version == 3


async def test_preserves_existing_unique_id(
    hass: HomeAssistant,
) -> None:
    """Test setup does not overwrite existing unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://example.com",
            CONF_USERNAME: "dummy",
            CONF_PASSWORD: "dummypw",
        },
        unique_id="existing-unique-id",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.unique_id == "existing-unique-id"
    assert entry.minor_version == 3


async def test_migration_keeps_minor_2_when_serial_missing(
    hass: HomeAssistant,
) -> None:
    """Test migration does not mark unique-id migration done without serial."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://example.com",
            CONF_USERNAME: "dummy",
            CONF_PASSWORD: "dummypw",
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    with patch("pyprusalink.PrusaLink.get_info", return_value={}):
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.unique_id is None
    assert entry.minor_version == 2


@pytest.mark.parametrize(
    "exception",
    [TimeoutError(), ConnectError("All connection attempts failed"), PrusaLinkError()],
)
async def test_migration_keeps_minor_2_on_transient_info_failures(
    hass: HomeAssistant,
    exception: Exception,
) -> None:
    """Test migration keeps retry state when fetching serial temporarily fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://example.com",
            CONF_USERNAME: "dummy",
            CONF_PASSWORD: "dummypw",
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "pyprusalink.PrusaLink.get_info",
        side_effect=[
            exception,
            {
                "nozzle_diameter": 0.40,
                "mmu": False,
                "serial": "serial-1337",
                "hostname": "PrusaXL",
                "min_extrusion_temp": 170,
                "location": "Workshop",
                "sd_ready": True,
                "farm_mode": False,
            },
        ],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.unique_id is None
    assert entry.minor_version == 2


async def test_migration_from_1_1_to_1_2_times_out(
    hass: HomeAssistant,
) -> None:
    """Test migration from version 1 keeps retry state on timeout."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://prusaxl.local",
            CONF_API_KEY: "api-key",
        },
        version=1,
    )
    entry.add_to_hass(hass)

    with patch("pyprusalink.PrusaLink.get_info", side_effect=TimeoutError()):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.minor_version == 1
    assert entry.unique_id is None


async def test_migration_from_1_2_to_1_3_migrates_entity_and_device_ids(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration to serial-based entity and device identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://example.com",
            CONF_USERNAME: "dummy",
            CONF_PASSWORD: "dummypw",
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    old_binary_unique_id = f"{entry.entry_id}_printer.status_connect"
    old_camera_unique_id = f"{entry.entry_id}_job_preview"

    old_binary = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        old_binary_unique_id,
        suggested_object_id="printer_status_connect",
        config_entry=entry,
    )
    old_camera = entity_registry.async_get_or_create(
        "camera",
        DOMAIN,
        old_camera_unique_id,
        suggested_object_id="job_preview",
        config_entry=entry,
    )

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
    )

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.minor_version == 3
    assert entry.unique_id == "serial-1337"

    migrated_binary = entity_registry.async_get(old_binary.entity_id)
    assert migrated_binary is not None
    assert migrated_binary.unique_id == "serial-1337_printer.status_connect"

    migrated_camera = entity_registry.async_get(old_camera.entity_id)
    assert migrated_camera is not None
    assert migrated_camera.unique_id == "serial-1337_job_preview"

    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)}) is None
    )
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, "serial-1337")})
        is not None
    )


async def test_migration_ignores_devices_without_old_identifier(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test migration skips unrelated devices on the same config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://example.com",
            CONF_USERNAME: "dummy",
            CONF_PASSWORD: "dummypw",
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    migrated_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
    )
    unrelated_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "already-serial")},
    )

    assert await hass.config_entries.async_setup(entry.entry_id)

    refreshed_migrated_device = device_registry.async_get(migrated_device.id)
    refreshed_device = device_registry.async_get(unrelated_device.id)
    assert refreshed_migrated_device is not None
    assert refreshed_migrated_device.identifiers == {(DOMAIN, "serial-1337")}
    assert refreshed_device is not None
    assert refreshed_device.identifiers == {(DOMAIN, "already-serial")}
    assert entry.unique_id == "serial-1337"
    assert entry.minor_version == 3


async def test_migration_skips_when_serial_is_already_used_by_another_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration keeps retry state when another entry already uses the serial."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://existing.example.com",
            CONF_USERNAME: "dummy",
            CONF_PASSWORD: "dummypw",
        },
        unique_id="serial-1337",
        version=1,
        minor_version=3,
    )
    existing_entry.add_to_hass(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://example.com",
            CONF_USERNAME: "dummy",
            CONF_PASSWORD: "dummypw",
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    old_unique_id = f"{entry.entry_id}_printer.status_connect"
    old_entity = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id="printer_status_connect",
        config_entry=entry,
    )
    old_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
    )

    assert await hass.config_entries.async_setup(entry.entry_id)

    migrated_entity = entity_registry.async_get(old_entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == old_unique_id

    refreshed_device = device_registry.async_get(old_device.id)
    assert refreshed_device is not None
    assert refreshed_device.identifiers == {(DOMAIN, entry.entry_id)}
    assert entry.unique_id is None
    assert entry.minor_version == 2


async def test_unloading(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test unloading prusalink."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert hass.states.async_entity_ids_count() > 0

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    for state in hass.states.async_all():
        assert state.state == "unavailable"


@pytest.mark.parametrize(
    "exception",
    [InvalidAuth, PrusaLinkError, ConnectError("All connection attempts failed")],
)
async def test_failed_update(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, exception
) -> None:
    """Test failed update marks prusalink unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    with (
        patch(
            "homeassistant.components.prusalink.PrusaLink.get_version",
            side_effect=exception,
        ),
        patch(
            "homeassistant.components.prusalink.PrusaLink.get_status",
            side_effect=exception,
        ),
        patch(
            "homeassistant.components.prusalink.PrusaLink.get_legacy_printer",
            side_effect=exception,
        ),
        patch(
            "homeassistant.components.prusalink.PrusaLink.get_job",
            side_effect=exception,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30), fire_all=True)
        await hass.async_block_till_done()

    for state in hass.states.async_all():
        assert state.state == "unavailable"


async def test_migration_from_1_1_to_1_2(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test migrating from version 1 to 2."""
    data = {
        CONF_HOST: "http://prusaxl.local",
        CONF_API_KEY: "api-key",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)

    # Ensure that we have username, password after migration
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        **data,
        CONF_USERNAME: "maker",
        CONF_PASSWORD: "api-key",
    }
    assert config_entries[0].minor_version == 3
    assert config_entries[0].unique_id == "serial-1337"
    # Make sure that we don't have any issues
    assert len(issue_registry.issues) == 0


async def test_migration_from_1_1_to_1_2_outdated_firmware(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test migrating from version 1.1 to 1.2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://prusaxl.local",
            CONF_API_KEY: "api-key",
        },
        version=1,
    )
    entry.add_to_hass(hass)

    with patch(
        "pyprusalink.PrusaLink.get_info",
        side_effect=InvalidAuth,  # Simulate firmware update required
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.minor_version == 1
    assert (DOMAIN, "firmware_5_1_required") in issue_registry.issues

    # Reloading the integration with a working API (e.g. User updated firmware)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Integration should be running now, the issue should be gone
    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 3
    assert entry.unique_id == "serial-1337"
    assert (DOMAIN, "firmware_5_1_required") not in issue_registry.issues


async def test_migration_fails_on_future_version(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test migrating fails on a version higher than the current one."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        version=PrusaLinkConfigFlow.VERSION + 1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migration_fails_on_future_minor_version(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test migrating fails on the current version with a higher minor version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        version=PrusaLinkConfigFlow.VERSION,
        minor_version=PrusaLinkConfigFlow.MINOR_VERSION + 1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
