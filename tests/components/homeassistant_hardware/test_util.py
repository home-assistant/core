"""Test hardware utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.hassio import AddonError, AddonInfo, AddonState
from homeassistant.components.homeassistant_hardware.helpers import (
    async_register_firmware_info_provider,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
    guess_firmware_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ZHA_CONFIG_ENTRY = MockConfigEntry(
    domain="zha",
    unique_id="some_unique_id",
    data={
        "device": {
            "path": "/dev/ttyUSB1",
            "baudrate": 115200,
            "flow_control": None,
        },
        "radio_type": "ezsp",
    },
    version=4,
)

ZHA_CONFIG_ENTRY2 = MockConfigEntry(
    domain="zha",
    unique_id="some_other_unique_id",
    data={
        "device": {
            "path": "/dev/ttyUSB2",
            "baudrate": 115200,
            "flow_control": None,
        },
        "radio_type": "ezsp",
    },
    version=4,
)


async def test_guess_firmware_info_unknown(hass: HomeAssistant) -> None:
    """Test guessing the firmware type."""

    await async_setup_component(hass, "homeassistant_hardware", {})

    assert (await guess_firmware_info(hass, "/dev/missing")) == FirmwareInfo(
        device="/dev/missing",
        firmware_type=ApplicationType.EZSP,
        firmware_version=None,
        source="unknown",
        owners=[],
    )


async def test_guess_firmware_info_integrations(hass: HomeAssistant) -> None:
    """Test guessing the firmware via OTBR and ZHA."""

    await async_setup_component(hass, "homeassistant_hardware", {})

    # One instance of ZHA and two OTBRs
    zha = MockConfigEntry(domain="zha", unique_id="some_unique_id_1")
    zha.add_to_hass(hass)

    otbr1 = MockConfigEntry(domain="otbr", unique_id="some_unique_id_2")
    otbr1.add_to_hass(hass)

    otbr2 = MockConfigEntry(domain="otbr", unique_id="some_unique_id_3")
    otbr2.add_to_hass(hass)

    # First ZHA is running with the stick
    zha_firmware_info = FirmwareInfo(
        device="/dev/serial/by-id/device1",
        firmware_type=ApplicationType.EZSP,
        firmware_version=None,
        source="zha",
        owners=[AsyncMock(is_running=AsyncMock(return_value=True))],
    )

    # First OTBR: neither the addon or the integration are loaded
    otbr_firmware_info1 = FirmwareInfo(
        device="/dev/serial/by-id/device1",
        firmware_type=ApplicationType.SPINEL,
        firmware_version=None,
        source="otbr",
        owners=[
            AsyncMock(is_running=AsyncMock(return_value=False)),
            AsyncMock(is_running=AsyncMock(return_value=False)),
        ],
    )

    # Second OTBR: fully running but is with an unrelated device
    otbr_firmware_info2 = FirmwareInfo(
        device="/dev/serial/by-id/device2",  # An unrelated device
        firmware_type=ApplicationType.SPINEL,
        firmware_version=None,
        source="otbr",
        owners=[
            AsyncMock(is_running=AsyncMock(return_value=True)),
            AsyncMock(is_running=AsyncMock(return_value=True)),
        ],
    )

    mock_zha_hardware_info = MagicMock(spec=["get_firmware_info"])
    mock_zha_hardware_info.get_firmware_info = MagicMock(return_value=zha_firmware_info)
    async_register_firmware_info_provider(hass, "zha", mock_zha_hardware_info)

    async def mock_otbr_async_get_firmware_info(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> FirmwareInfo | None:
        return {
            otbr1.entry_id: otbr_firmware_info1,
            otbr2.entry_id: otbr_firmware_info2,
        }.get(config_entry.entry_id)

    mock_otbr_hardware_info = MagicMock(spec=["async_get_firmware_info"])
    mock_otbr_hardware_info.async_get_firmware_info = AsyncMock(
        side_effect=mock_otbr_async_get_firmware_info
    )
    async_register_firmware_info_provider(hass, "otbr", mock_otbr_hardware_info)

    # ZHA wins for the first stick, since it's actually running
    assert (
        await guess_firmware_info(hass, "/dev/serial/by-id/device1")
    ) == zha_firmware_info

    # Second stick is communicating exclusively with the second OTBR
    assert (
        await guess_firmware_info(hass, "/dev/serial/by-id/device2")
    ) == otbr_firmware_info2

    # If we stop ZHA, OTBR will take priority
    zha_firmware_info.owners[0].is_running.return_value = False
    otbr_firmware_info1.owners[0].is_running.return_value = True
    assert (
        await guess_firmware_info(hass, "/dev/serial/by-id/device1")
    ) == otbr_firmware_info1


async def test_owning_addon(hass: HomeAssistant) -> None:
    """Test `OwningAddon`."""

    owning_addon = OwningAddon(slug="some-addon-slug")

    # Explicitly running
    with patch(
        "homeassistant.components.homeassistant_hardware.util.WaitingAddonManager"
    ) as mock_manager:
        mock_manager.return_value.async_get_addon_info = AsyncMock(
            return_value=AddonInfo(
                available=True,
                hostname="core_some_addon_slug",
                options={},
                state=AddonState.RUNNING,
                update_available=False,
                version="1.0.0",
            )
        )
        assert (await owning_addon.is_running(hass)) is True

    # Explicitly not running
    with patch(
        "homeassistant.components.homeassistant_hardware.util.WaitingAddonManager"
    ) as mock_manager:
        mock_manager.return_value.async_get_addon_info = AsyncMock(
            return_value=AddonInfo(
                available=True,
                hostname="core_some_addon_slug",
                options={},
                state=AddonState.NOT_RUNNING,
                update_available=False,
                version="1.0.0",
            )
        )
        assert (await owning_addon.is_running(hass)) is False

    # Failed to get status
    with patch(
        "homeassistant.components.homeassistant_hardware.util.WaitingAddonManager"
    ) as mock_manager:
        mock_manager.return_value.async_get_addon_info = AsyncMock(
            side_effect=AddonError()
        )
        assert (await owning_addon.is_running(hass)) is False


async def test_owning_integration(hass: HomeAssistant) -> None:
    """Test `OwningIntegration`."""
    config_entry = MockConfigEntry(domain="mock_domain", unique_id="some_unique_id")
    config_entry.add_to_hass(hass)

    owning_integration = OwningIntegration(config_entry_id=config_entry.entry_id)

    # Explicitly running
    config_entry.mock_state(hass, ConfigEntryState.LOADED)
    assert (await owning_integration.is_running(hass)) is True

    # Explicitly not running
    config_entry.mock_state(hass, ConfigEntryState.NOT_LOADED)
    assert (await owning_integration.is_running(hass)) is False

    # Missing config entry
    owning_integration2 = OwningIntegration(config_entry_id="some_nonexistenct_id")
    assert (await owning_integration2.is_running(hass)) is False


async def test_firmware_info(hass: HomeAssistant) -> None:
    """Test `FirmwareInfo`."""

    owner1 = AsyncMock()
    owner2 = AsyncMock()

    firmware_info = FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.EZSP,
        firmware_version="1.0.0",
        source="zha",
        owners=[owner1, owner2],
    )

    # Both running
    owner1.is_running.return_value = True
    owner2.is_running.return_value = True
    assert (await firmware_info.is_running(hass)) is True

    # Only one running
    owner1.is_running.return_value = True
    owner2.is_running.return_value = False
    assert (await firmware_info.is_running(hass)) is False

    # No owners
    firmware_info2 = FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.EZSP,
        firmware_version="1.0.0",
        source="zha",
        owners=[],
    )

    assert (await firmware_info2.is_running(hass)) is False
