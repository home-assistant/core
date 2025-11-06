"""Test Home Assistant Hardware beta firmware switch entity."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import Mock, call, patch

import pytest

from homeassistant.components.homeassistant_hardware.coordinator import (
    FirmwareUpdateCoordinator,
)
from homeassistant.components.homeassistant_hardware.switch import (
    BaseBetaFirmwareSwitch,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import async_setup_component

from .common import TEST_DOMAIN, TEST_FIRMWARE_RELEASES_URL, TEST_MANIFEST

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache,
)

TEST_DEVICE = "/dev/serial/by-id/test-device-12345"
TEST_SWITCH_ENTITY_ID = "switch.mock_device_beta_firmware_updates"


class MockBetaFirmwareSwitch(BaseBetaFirmwareSwitch):
    """Mock beta firmware switch for testing."""

    def __init__(
        self,
        coordinator: FirmwareUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the mock beta firmware switch."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = "beta_firmware"
        self._attr_name = "Beta firmware updates"
        self._attr_device_info = DeviceInfo(
            identifiers={(TEST_DOMAIN, "test_device")},
            name="Mock Device",
            model="Mock Model",
            manufacturer="Mock Manufacturer",
        )


def _mock_async_create_switch_entity(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> MockBetaFirmwareSwitch:
    """Create a mock switch entity."""
    session = async_get_clientsession(hass)
    coordinator = FirmwareUpdateCoordinator(
        hass,
        config_entry,
        session,
        TEST_FIRMWARE_RELEASES_URL,
    )
    entity = MockBetaFirmwareSwitch(coordinator, config_entry)
    async_add_entities([entity])
    return entity


async def mock_async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Set up test config entry."""
    await hass.config_entries.async_forward_entry_setups(
        config_entry, [Platform.SWITCH]
    )
    return True


async def mock_async_setup_switch_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the beta firmware switch config entry."""
    _mock_async_create_switch_entity(hass, config_entry, async_add_entities)


@pytest.fixture(name="mock_firmware_client")
def mock_firmware_client_fixture():
    """Create a mock firmware update client."""
    with patch(
        "homeassistant.components.homeassistant_hardware.coordinator.FirmwareUpdateClient",
        autospec=True,
    ) as mock_client:
        mock_client.return_value.async_update_data.return_value = TEST_MANIFEST
        mock_client.return_value.update_prerelease = Mock()
        yield mock_client.return_value


@pytest.fixture(name="switch_config_entry")
async def mock_switch_config_entry(
    hass: HomeAssistant,
    mock_firmware_client,
) -> AsyncGenerator[ConfigEntry]:
    """Set up a mock config entry for testing."""
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
        "test.switch",
        MockPlatform(async_setup_entry=mock_async_setup_switch_entities),
    )

    # Set up a mock integration using the hardware switch entity
    config_entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            "device": TEST_DEVICE,
        },
    )
    config_entry.add_to_hass(hass)

    with mock_config_flow(TEST_DOMAIN, ConfigFlow):
        yield config_entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_default_off_state(
    hass: HomeAssistant,
    switch_config_entry: ConfigEntry,
    mock_firmware_client,
) -> None:
    """Test switch defaults to off when no previous state."""
    assert await hass.config_entries.async_setup(switch_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    # Verify coordinator was called with False during setup
    assert mock_firmware_client.update_prerelease.mock_calls == [call(False)]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("initial_state", "expected_state", "expected_prerelease"),
    [
        (STATE_ON, STATE_ON, True),
        (STATE_OFF, STATE_OFF, False),
    ],
)
async def test_switch_restore_state(
    hass: HomeAssistant,
    switch_config_entry: ConfigEntry,
    mock_firmware_client,
    initial_state: str,
    expected_state: str,
    expected_prerelease: bool,
) -> None:
    """Test switch restores previous state and has correct entity attributes."""
    mock_restore_cache(hass, [State(TEST_SWITCH_ENTITY_ID, initial_state)])

    assert await hass.config_entries.async_setup(switch_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get("friendly_name") == "Mock Device Beta firmware updates"

    # Verify coordinator was called with correct value during setup
    assert mock_firmware_client.update_prerelease.mock_calls == [
        call(expected_prerelease)
    ]

    # Verify entity registry attributes
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(TEST_SWITCH_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.entity_category == EntityCategory.CONFIG
    assert entity_entry.translation_key == "beta_firmware"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("service", "target_state", "expected_prerelease"),
    [
        (SERVICE_TURN_ON, STATE_ON, True),
        (SERVICE_TURN_OFF, STATE_OFF, False),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    switch_config_entry: ConfigEntry,
    mock_firmware_client,
    service: str,
    target_state: str,
    expected_prerelease: bool,
) -> None:
    """Test turning switch on/off updates state and coordinator."""

    # Start with opposite state
    mock_restore_cache(
        hass,
        [
            State(
                TEST_SWITCH_ENTITY_ID,
                STATE_ON if service == SERVICE_TURN_OFF else STATE_OFF,
            )
        ],
    )

    # Track async_refresh calls
    with patch(
        "homeassistant.components.homeassistant_hardware.coordinator.FirmwareUpdateCoordinator.async_refresh"
    ) as mock_refresh:
        assert await hass.config_entries.async_setup(switch_config_entry.entry_id)
        await hass.async_block_till_done()

        # Reset mocks after setup
        mock_firmware_client.update_prerelease.reset_mock()
        mock_refresh.reset_mock()

        # Call the service
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: TEST_SWITCH_ENTITY_ID},
            blocking=True,
        )

    # Verify state changed
    state = hass.states.get(TEST_SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == target_state

    # Verify coordinator methods were called
    assert mock_firmware_client.update_prerelease.mock_calls == [
        call(expected_prerelease)
    ]
    assert len(mock_refresh.mock_calls) == 1
