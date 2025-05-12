"""Test Home Assistant Hardware firmware update entity."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import dataclasses
import logging
from unittest.mock import Mock, patch

import aiohttp
from ha_silabs_firmware_client import FirmwareManifest, FirmwareMetadata
import pytest
from yarl import URL

from homeassistant.components.homeassistant_hardware.coordinator import (
    FirmwareUpdateCoordinator,
)
from homeassistant.components.homeassistant_hardware.helpers import (
    async_notify_firmware_info,
    async_register_firmware_info_provider,
)
from homeassistant.components.homeassistant_hardware.update import (
    BaseFirmwareUpdateEntity,
    FirmwareUpdateEntityDescription,
    FirmwareUpdateExtraStoredData,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningIntegration,
)
from homeassistant.components.update import UpdateDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import EVENT_STATE_CHANGED, EntityCategory
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    HomeAssistantError,
    State,
    callback,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    async_capture_events,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache_with_extra_data,
)

TEST_DOMAIN = "test"
TEST_DEVICE = "/dev/serial/by-id/some-unique-serial-device-12345"
TEST_FIRMWARE_RELEASES_URL = "https://example.org/firmware"
TEST_UPDATE_ENTITY_ID = "update.mock_name_firmware"
TEST_MANIFEST = FirmwareManifest(
    url=URL("https://example.org/firmware"),
    html_url=URL("https://example.org/release_notes"),
    created_at=dt_util.utcnow(),
    firmwares=(
        FirmwareMetadata(
            filename="skyconnect_zigbee_ncp_test.gbl",
            checksum="aaa",
            size=123,
            release_notes="Some release notes go here",
            metadata={
                "baudrate": 115200,
                "ezsp_version": "7.4.4.0",
                "fw_type": "zigbee_ncp",
                "fw_variant": None,
                "metadata_version": 2,
                "sdk_version": "4.4.4",
            },
            url=URL("https://example.org/firmwares/skyconnect_zigbee_ncp_test.gbl"),
        ),
    ),
)


TEST_FIRMWARE_ENTITY_DESCRIPTIONS: dict[
    ApplicationType | None, FirmwareUpdateEntityDescription
] = {
    ApplicationType.EZSP: FirmwareUpdateEntityDescription(
        key="firmware",
        display_precision=0,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        version_parser=lambda fw: fw.split(" ", 1)[0],
        fw_type="skyconnect_zigbee_ncp",
        version_key="ezsp_version",
        expected_firmware_type=ApplicationType.EZSP,
        firmware_name="EmberZNet",
    ),
    ApplicationType.SPINEL: FirmwareUpdateEntityDescription(
        key="firmware",
        display_precision=0,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        version_parser=lambda fw: fw.split("/", 1)[1].split("_", 1)[0],
        fw_type="skyconnect_openthread_rcp",
        version_key="ot_rcp_version",
        expected_firmware_type=ApplicationType.SPINEL,
        firmware_name="OpenThread RCP",
    ),
    None: FirmwareUpdateEntityDescription(
        key="firmware",
        display_precision=0,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        version_parser=lambda fw: fw,
        fw_type=None,
        version_key=None,
        expected_firmware_type=None,
        firmware_name=None,
    ),
}


def _mock_async_create_update_entity(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    session: aiohttp.ClientSession,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> MockFirmwareUpdateEntity:
    """Create an update entity that handles firmware type changes."""
    firmware_type = config_entry.data["firmware"]
    entity_description = TEST_FIRMWARE_ENTITY_DESCRIPTIONS[
        ApplicationType(firmware_type) if firmware_type is not None else None
    ]

    entity = MockFirmwareUpdateEntity(
        device=config_entry.data["device"],
        config_entry=config_entry,
        update_coordinator=FirmwareUpdateCoordinator(
            hass,
            session,
            TEST_FIRMWARE_RELEASES_URL,
        ),
        entity_description=entity_description,
    )

    def firmware_type_changed(
        old_type: ApplicationType | None, new_type: ApplicationType | None
    ) -> None:
        """Replace the current entity when the firmware type changes."""
        er.async_get(hass).async_remove(entity.entity_id)
        async_add_entities(
            [
                _mock_async_create_update_entity(
                    hass, config_entry, session, async_add_entities
                )
            ]
        )

    entity.async_on_remove(
        entity.add_firmware_type_changed_callback(firmware_type_changed)
    )

    return entity


async def mock_async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Set up test config entry."""
    await hass.config_entries.async_forward_entry_setups(config_entry, ["update"])
    return True


async def mock_async_setup_update_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the firmware update config entry."""
    session = async_get_clientsession(hass)
    entity = _mock_async_create_update_entity(
        hass, config_entry, session, async_add_entities
    )

    async_add_entities([entity])


class MockFirmwareUpdateEntity(BaseFirmwareUpdateEntity):
    """Mock SkyConnect firmware update entity."""

    bootloader_reset_type = None

    def __init__(
        self,
        device: str,
        config_entry: ConfigEntry,
        update_coordinator: FirmwareUpdateCoordinator,
        entity_description: FirmwareUpdateEntityDescription,
    ) -> None:
        """Initialize the mock SkyConnect firmware update entity."""
        super().__init__(device, config_entry, update_coordinator, entity_description)
        self._attr_unique_id = self.entity_description.key
        self._attr_device_info = DeviceInfo(
            identifiers={(TEST_DOMAIN, "yellow")},
            name="Mock Name",
            model="Mock Model",
            manufacturer="Mock Manufacturer",
        )

        # Use the cached firmware info if it exists
        if self._config_entry.data["firmware"] is not None:
            self._current_firmware_info = FirmwareInfo(
                device=device,
                firmware_type=ApplicationType(self._config_entry.data["firmware"]),
                firmware_version=self._config_entry.data["firmware_version"],
                owners=[],
                source=TEST_DOMAIN,
            )

    @callback
    def _firmware_info_callback(self, firmware_info: FirmwareInfo) -> None:
        """Handle updated firmware info being pushed by an integration."""
        super()._firmware_info_callback(firmware_info)

        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data={
                **self._config_entry.data,
                "firmware": firmware_info.firmware_type,
                "firmware_version": firmware_info.firmware_version,
            },
        )


@pytest.fixture(name="update_config_entry")
async def mock_update_config_entry(
    hass: HomeAssistant,
) -> AsyncGenerator[ConfigEntry]:
    """Set up a mock Home Assistant Hardware firmware update entity."""
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "homeassistant_hardware", {})

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=mock_async_setup_entry,
        ),
        built_in=False,
    )
    mock_platform(hass, "test.config_flow")
    mock_platform(
        hass,
        "test.update",
        MockPlatform(async_setup_entry=mock_async_setup_update_entities),
    )

    # Set up a mock integration using the hardware update entity
    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "device": TEST_DEVICE,
            "firmware": "ezsp",
            "firmware_version": "7.3.1.0 build 0",
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.coordinator.FirmwareUpdateClient",
            autospec=True,
        ) as mock_update_client,
        mock_config_flow(TEST_DOMAIN, ConfigFlow),
    ):
        mock_update_client.return_value.async_update_data.return_value = TEST_MANIFEST
        yield config_entry


async def test_update_entity_installation(
    hass: HomeAssistant, update_config_entry: ConfigEntry
) -> None:
    """Test the Hardware firmware update entity installation."""

    assert await hass.config_entries.async_setup(update_config_entry.entry_id)
    await hass.async_block_till_done()

    # Set up another integration communicating with the device
    owning_config_entry = MockConfigEntry(
        domain="another_integration",
        data={
            "device": {
                "path": TEST_DEVICE,
                "flow_control": "hardware",
                "baudrate": 115200,
            },
            "radio_type": "ezsp",
        },
        version=4,
    )
    owning_config_entry.add_to_hass(hass)
    owning_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    # The integration provides firmware info
    mock_hw_module = Mock()
    mock_hw_module.get_firmware_info = lambda hass, config_entry: FirmwareInfo(
        device=TEST_DEVICE,
        firmware_type=ApplicationType.EZSP,
        firmware_version="7.3.1.0 build 0",
        owners=[OwningIntegration(config_entry_id=config_entry.entry_id)],
        source="another_integration",
    )

    async_register_firmware_info_provider(hass, "another_integration", mock_hw_module)

    # Pretend the other integration loaded and notified hardware of the running firmware
    await async_notify_firmware_info(
        hass,
        "another_integration",
        mock_hw_module.get_firmware_info(hass, owning_config_entry),
    )

    state_before_update = hass.states.get(TEST_UPDATE_ENTITY_ID)
    assert state_before_update is not None
    assert state_before_update.state == "unknown"
    assert state_before_update.attributes["title"] == "EmberZNet"
    assert state_before_update.attributes["installed_version"] == "7.3.1.0"
    assert state_before_update.attributes["latest_version"] is None

    # When we check for an update, one will be shown
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": TEST_UPDATE_ENTITY_ID},
        blocking=True,
    )
    state_after_update = hass.states.get(TEST_UPDATE_ENTITY_ID)
    assert state_after_update is not None
    assert state_after_update.state == "on"
    assert state_after_update.attributes["title"] == "EmberZNet"
    assert state_after_update.attributes["installed_version"] == "7.3.1.0"
    assert state_after_update.attributes["latest_version"] == "7.4.4.0"
    assert state_after_update.attributes["release_summary"] == (
        "Some release notes go here"
    )
    assert state_after_update.attributes["release_url"] == (
        "https://example.org/release_notes"
    )

    async def mock_flash_firmware(
        hass: HomeAssistant,
        device: str,
        fw_data: bytes,
        expected_installed_firmware_type: ApplicationType,
        bootloader_reset_type: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> FirmwareInfo:
        await asyncio.sleep(0)
        progress_callback(0, 100)
        await asyncio.sleep(0)
        progress_callback(50, 100)
        await asyncio.sleep(0)
        progress_callback(100, 100)

        return FirmwareInfo(
            device=TEST_DEVICE,
            firmware_type=ApplicationType.EZSP,
            firmware_version="7.4.4.0 build 0",
            owners=[],
            source="probe",
        )

    # When we install it, the other integration is reloaded
    with (
        patch(
            "homeassistant.components.homeassistant_hardware.update.async_flash_silabs_firmware",
            side_effect=mock_flash_firmware,
        ),
    ):
        state_changes: list[Event[EventStateChangedData]] = async_capture_events(
            hass, EVENT_STATE_CHANGED
        )
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": TEST_UPDATE_ENTITY_ID},
            blocking=True,
        )

    # Progress events are emitted during the installation
    assert len(state_changes) == 7

    # Indeterminate progress first
    assert state_changes[0].data["new_state"].attributes["in_progress"] is True
    assert state_changes[0].data["new_state"].attributes["update_percentage"] is None

    # Then the update starts
    assert state_changes[1].data["new_state"].attributes["update_percentage"] == 0
    assert state_changes[2].data["new_state"].attributes["update_percentage"] == 50
    assert state_changes[3].data["new_state"].attributes["update_percentage"] == 100

    # Once it is done, we probe the firmware
    assert state_changes[4].data["new_state"].attributes["in_progress"] is True
    assert state_changes[4].data["new_state"].attributes["update_percentage"] is None

    # Finally, the update finishes
    assert state_changes[5].data["new_state"].attributes["update_percentage"] is None
    assert state_changes[6].data["new_state"].attributes["update_percentage"] is None
    assert state_changes[6].data["new_state"].attributes["in_progress"] is False

    # After the firmware update, the entity has the new version and the correct state
    state_after_install = hass.states.get(TEST_UPDATE_ENTITY_ID)
    assert state_after_install is not None
    assert state_after_install.state == "off"
    assert state_after_install.attributes["title"] == "EmberZNet"
    assert state_after_install.attributes["installed_version"] == "7.4.4.0"
    assert state_after_install.attributes["latest_version"] == "7.4.4.0"


async def test_update_entity_installation_failure(
    hass: HomeAssistant, update_config_entry: ConfigEntry
) -> None:
    """Test installation failing during flashing."""
    assert await hass.config_entries.async_setup(update_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": TEST_UPDATE_ENTITY_ID},
        blocking=True,
    )

    state_before_install = hass.states.get(TEST_UPDATE_ENTITY_ID)
    assert state_before_install is not None
    assert state_before_install.state == "on"
    assert state_before_install.attributes["title"] == "EmberZNet"
    assert state_before_install.attributes["installed_version"] == "7.3.1.0"
    assert state_before_install.attributes["latest_version"] == "7.4.4.0"

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.update.async_flash_silabs_firmware",
            side_effect=HomeAssistantError("Failed to flash firmware"),
        ),
        pytest.raises(HomeAssistantError, match="Failed to flash firmware"),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": TEST_UPDATE_ENTITY_ID},
            blocking=True,
        )

    # After the firmware update fails, we can still try again
    state_after_install = hass.states.get(TEST_UPDATE_ENTITY_ID)
    assert state_after_install is not None
    assert state_after_install.state == "on"
    assert state_after_install.attributes["title"] == "EmberZNet"
    assert state_after_install.attributes["installed_version"] == "7.3.1.0"
    assert state_after_install.attributes["latest_version"] == "7.4.4.0"


async def test_update_entity_installation_probe_failure(
    hass: HomeAssistant, update_config_entry: ConfigEntry
) -> None:
    """Test installation failing during post-flashing probing."""
    assert await hass.config_entries.async_setup(update_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": TEST_UPDATE_ENTITY_ID},
        blocking=True,
    )

    state_before_install = hass.states.get(TEST_UPDATE_ENTITY_ID)
    assert state_before_install is not None
    assert state_before_install.state == "on"
    assert state_before_install.attributes["title"] == "EmberZNet"
    assert state_before_install.attributes["installed_version"] == "7.3.1.0"
    assert state_before_install.attributes["latest_version"] == "7.4.4.0"

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.update.async_flash_silabs_firmware",
            side_effect=HomeAssistantError(
                "Failed to probe the firmware after flashing"
            ),
        ),
        pytest.raises(
            HomeAssistantError, match="Failed to probe the firmware after flashing"
        ),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": TEST_UPDATE_ENTITY_ID},
            blocking=True,
        )

    # After the firmware update fails, we can still try again
    state_after_install = hass.states.get(TEST_UPDATE_ENTITY_ID)
    assert state_after_install is not None
    assert state_after_install.state == "on"
    assert state_after_install.attributes["title"] == "EmberZNet"
    assert state_after_install.attributes["installed_version"] == "7.3.1.0"
    assert state_after_install.attributes["latest_version"] == "7.4.4.0"


async def test_update_entity_state_restoration(
    hass: HomeAssistant, update_config_entry: ConfigEntry
) -> None:
    """Test the Hardware firmware update entity state restoration."""

    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(TEST_UPDATE_ENTITY_ID, "on"),
                FirmwareUpdateExtraStoredData(
                    firmware_manifest=TEST_MANIFEST
                ).as_dict(),
            )
        ],
    )

    assert await hass.config_entries.async_setup(update_config_entry.entry_id)
    await hass.async_block_till_done()

    # The state is correctly restored
    state = hass.states.get(TEST_UPDATE_ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["title"] == "EmberZNet"
    assert state.attributes["installed_version"] == "7.3.1.0"
    assert state.attributes["latest_version"] == "7.4.4.0"
    assert state.attributes["release_summary"] == ("Some release notes go here")
    assert state.attributes["release_url"] == ("https://example.org/release_notes")


async def test_update_entity_firmware_missing_from_manifest(
    hass: HomeAssistant, update_config_entry: ConfigEntry
) -> None:
    """Test the Hardware firmware update entity handles missing firmware."""

    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(TEST_UPDATE_ENTITY_ID, "on"),
                # Ensure the manifest does not contain our expected firmware type
                FirmwareUpdateExtraStoredData(
                    firmware_manifest=dataclasses.replace(TEST_MANIFEST, firmwares=())
                ).as_dict(),
            )
        ],
    )

    assert await hass.config_entries.async_setup(update_config_entry.entry_id)
    await hass.async_block_till_done()

    # The state is restored, accounting for the missing firmware
    state = hass.states.get(TEST_UPDATE_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["title"] == "EmberZNet"
    assert state.attributes["installed_version"] == "7.3.1.0"
    assert state.attributes["latest_version"] is None
    assert state.attributes["release_summary"] is None
    assert state.attributes["release_url"] is None


async def test_update_entity_graceful_firmware_type_callback_errors(
    hass: HomeAssistant,
    update_config_entry: ConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test firmware update entity handling of firmware type callback errors."""

    session = async_get_clientsession(hass)
    update_entity = MockFirmwareUpdateEntity(
        device=TEST_DEVICE,
        config_entry=update_config_entry,
        update_coordinator=FirmwareUpdateCoordinator(
            hass,
            session,
            TEST_FIRMWARE_RELEASES_URL,
        ),
        entity_description=TEST_FIRMWARE_ENTITY_DESCRIPTIONS[ApplicationType.EZSP],
    )
    update_entity.hass = hass
    await update_entity.async_added_to_hass()

    callback = Mock(side_effect=RuntimeError("Callback failed"))
    unregister_callback = update_entity.add_firmware_type_changed_callback(callback)

    with caplog.at_level(logging.WARNING):
        await async_notify_firmware_info(
            hass,
            "some_integration",
            FirmwareInfo(
                device=TEST_DEVICE,
                firmware_type=ApplicationType.SPINEL,
                firmware_version="SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4; EFR32; Oct 21 2024 14:40:57",
                owners=[],
                source="probe",
            ),
        )

    unregister_callback()
    assert "Failed to call firmware type changed callback" in caplog.text
