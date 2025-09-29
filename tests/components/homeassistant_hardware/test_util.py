"""Test hardware utilities."""

import asyncio
from collections.abc import Callable
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, call, patch

import pytest
from universal_silabs_flasher.common import Version as FlasherVersion
from universal_silabs_flasher.const import ApplicationType as FlasherApplicationType
from universal_silabs_flasher.firmware import GBLImage

from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.components.homeassistant_hardware.helpers import (
    async_register_firmware_info_provider,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
    async_flash_silabs_firmware,
    get_otbr_addon_firmware_info,
    guess_firmware_info,
    probe_silabs_firmware_info,
    probe_silabs_firmware_type,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .test_config_flow import create_mock_owner

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


async def test_owning_addon_temporarily_stop_info_error(hass: HomeAssistant) -> None:
    """Test `OwningAddon` temporarily stopping with an info error."""

    owning_addon = OwningAddon(slug="some-addon-slug")
    mock_manager = AsyncMock()
    mock_manager.async_get_addon_info.side_effect = AddonError()

    with patch(
        "homeassistant.components.homeassistant_hardware.util.WaitingAddonManager",
        return_value=mock_manager,
    ):
        async with owning_addon.temporarily_stop(hass):
            pass

    # We never restart it
    assert len(mock_manager.async_get_addon_info.mock_calls) == 1
    assert len(mock_manager.async_stop_addon.mock_calls) == 0
    assert len(mock_manager.async_wait_until_addon_state.mock_calls) == 0
    assert len(mock_manager.async_start_addon_waiting.mock_calls) == 0


async def test_owning_addon_temporarily_stop_not_running(hass: HomeAssistant) -> None:
    """Test `OwningAddon` temporarily stopping when the addon is not running."""

    owning_addon = OwningAddon(slug="some-addon-slug")

    mock_manager = AsyncMock()
    mock_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname="core_some_addon_slug",
        options={},
        state=AddonState.NOT_RUNNING,
        update_available=False,
        version="1.0.0",
    )

    with patch(
        "homeassistant.components.homeassistant_hardware.util.WaitingAddonManager",
        return_value=mock_manager,
    ):
        async with owning_addon.temporarily_stop(hass):
            pass

    # We never restart it
    assert len(mock_manager.async_get_addon_info.mock_calls) == 1
    assert len(mock_manager.async_stop_addon.mock_calls) == 0
    assert len(mock_manager.async_wait_until_addon_state.mock_calls) == 0
    assert len(mock_manager.async_start_addon_waiting.mock_calls) == 0


async def test_owning_addon_temporarily_stop(hass: HomeAssistant) -> None:
    """Test `OwningAddon` temporarily stopping when the addon is running."""

    owning_addon = OwningAddon(slug="some-addon-slug")

    mock_manager = AsyncMock()
    mock_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname="core_some_addon_slug",
        options={},
        state=AddonState.RUNNING,
        update_available=False,
        version="1.0.0",
    )

    mock_manager.async_stop_addon = AsyncMock()
    mock_manager.async_wait_until_addon_state = AsyncMock()
    mock_manager.async_start_addon_waiting = AsyncMock()

    # The error is propagated but it doesn't affect restarting the addon
    with (
        patch(
            "homeassistant.components.homeassistant_hardware.util.WaitingAddonManager",
            return_value=mock_manager,
        ),
        pytest.raises(RuntimeError),
    ):
        async with owning_addon.temporarily_stop(hass):
            raise RuntimeError("Some error")

    # We restart it
    assert len(mock_manager.async_get_addon_info.mock_calls) == 1
    assert len(mock_manager.async_stop_addon.mock_calls) == 1
    assert len(mock_manager.async_wait_until_addon_state.mock_calls) == 1
    assert len(mock_manager.async_start_addon_waiting.mock_calls) == 1


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


async def test_owning_integration_temporarily_stop_missing_entry(
    hass: HomeAssistant,
) -> None:
    """Test temporarily stopping the integration when the config entry doesn't exist."""
    missing_integration = OwningIntegration(config_entry_id="missing_entry_id")

    with (
        patch.object(hass.config_entries, "async_unload") as mock_unload,
        patch.object(hass.config_entries, "async_setup") as mock_setup,
    ):
        async with missing_integration.temporarily_stop(hass):
            pass

    # Because there's no matching entry, no unload or setup calls are made
    assert len(mock_unload.mock_calls) == 0
    assert len(mock_setup.mock_calls) == 0


async def test_owning_integration_temporarily_stop_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Test temporarily stopping the integration when the config entry is not loaded."""
    entry = MockConfigEntry(domain="test_domain")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    integration = OwningIntegration(config_entry_id=entry.entry_id)

    with (
        patch.object(hass.config_entries, "async_unload") as mock_unload,
        patch.object(hass.config_entries, "async_setup") as mock_setup,
    ):
        async with integration.temporarily_stop(hass):
            pass

    # Since the entry was not loaded, we never unload or re-setup
    assert len(mock_unload.mock_calls) == 0
    assert len(mock_setup.mock_calls) == 0


async def test_owning_integration_temporarily_stop_loaded(hass: HomeAssistant) -> None:
    """Test temporarily stopping the integration when the config entry is loaded."""
    entry = MockConfigEntry(domain="test_domain")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    integration = OwningIntegration(config_entry_id=entry.entry_id)

    with (
        patch.object(hass.config_entries, "async_unload") as mock_unload,
        patch.object(hass.config_entries, "async_setup") as mock_setup,
        pytest.raises(RuntimeError),
    ):
        async with integration.temporarily_stop(hass):
            raise RuntimeError("Some error during the temporary stop")

    # We expect one unload followed by one setup call
    mock_unload.assert_called_once_with(entry.entry_id)
    mock_setup.assert_called_once_with(entry.entry_id)


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


async def test_get_otbr_addon_firmware_info_failure(hass: HomeAssistant) -> None:
    """Test getting OTBR addon firmware info failure due to bad API call."""

    otbr_addon_manager = AsyncMock(spec_set=AddonManager)
    otbr_addon_manager.async_get_addon_info.side_effect = AddonError()

    assert (await get_otbr_addon_firmware_info(hass, otbr_addon_manager)) is None


async def test_get_otbr_addon_firmware_info_failure_bad_options(
    hass: HomeAssistant,
) -> None:
    """Test getting OTBR addon firmware info failure due to bad addon options."""

    otbr_addon_manager = AsyncMock(spec_set=AddonManager)
    otbr_addon_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname="core_some_addon_slug",
        options={},  # `device` is missing
        state=AddonState.RUNNING,
        update_available=False,
        version="1.0.0",
    )

    assert (await get_otbr_addon_firmware_info(hass, otbr_addon_manager)) is None


@pytest.mark.parametrize(
    ("app_type", "firmware_version", "expected_fw_info"),
    [
        (
            FlasherApplicationType.EZSP,
            FlasherVersion("1.0.0"),
            FirmwareInfo(
                device="/dev/ttyUSB0",
                firmware_type=ApplicationType.EZSP,
                firmware_version="1.0.0",
                source="probe",
                owners=[],
            ),
        ),
        (
            FlasherApplicationType.EZSP,
            None,
            FirmwareInfo(
                device="/dev/ttyUSB0",
                firmware_type=ApplicationType.EZSP,
                firmware_version=None,
                source="probe",
                owners=[],
            ),
        ),
        (
            FlasherApplicationType.SPINEL,
            FlasherVersion("2.0.0"),
            FirmwareInfo(
                device="/dev/ttyUSB0",
                firmware_type=ApplicationType.SPINEL,
                firmware_version="2.0.0",
                source="probe",
                owners=[],
            ),
        ),
        (None, None, None),
    ],
)
async def test_probe_silabs_firmware_info(
    app_type: FlasherApplicationType | None,
    firmware_version: FlasherVersion | None,
    expected_fw_info: FirmwareInfo | None,
) -> None:
    """Test getting the firmware info."""

    def probe_app_type() -> None:
        mock_flasher.app_type = app_type
        mock_flasher.app_version = firmware_version

    mock_flasher = MagicMock()
    mock_flasher.app_type = None
    mock_flasher.app_version = None
    mock_flasher.probe_app_type = AsyncMock(side_effect=probe_app_type)

    with patch(
        "homeassistant.components.homeassistant_hardware.util.Flasher",
        return_value=mock_flasher,
    ):
        result = await probe_silabs_firmware_info("/dev/ttyUSB0")
        assert result == expected_fw_info


@pytest.mark.parametrize(
    ("probe_result", "expected"),
    [
        (
            FirmwareInfo(
                device="/dev/ttyUSB0",
                firmware_type=ApplicationType.EZSP,
                firmware_version=None,
                source="unknown",
                owners=[],
            ),
            ApplicationType.EZSP,
        ),
        (None, None),
    ],
)
async def test_probe_silabs_firmware_type(
    probe_result: FirmwareInfo | None, expected: ApplicationType | None
) -> None:
    """Test getting the firmware type from the probe result."""
    with patch(
        "homeassistant.components.homeassistant_hardware.util.probe_silabs_firmware_info",
        autospec=True,
        return_value=probe_result,
    ):
        result = await probe_silabs_firmware_type("/dev/ttyUSB0")
        assert result == expected


async def test_async_flash_silabs_firmware(hass: HomeAssistant) -> None:
    """Test async_flash_silabs_firmware."""
    owner1 = create_mock_owner()
    owner2 = create_mock_owner()

    progress_callback = Mock()

    async def mock_flash_firmware(
        fw_image: GBLImage, progress_callback: Callable[[int, int], None]
    ) -> None:
        """Mock flash firmware function."""
        await asyncio.sleep(0)
        progress_callback(0, 100)
        await asyncio.sleep(0)
        progress_callback(50, 100)
        await asyncio.sleep(0)
        progress_callback(100, 100)
        await asyncio.sleep(0)

    mock_flasher = Mock()
    mock_flasher.enter_bootloader = AsyncMock()
    mock_flasher.flash_firmware = AsyncMock(side_effect=mock_flash_firmware)

    expected_firmware_info = FirmwareInfo(
        device="/dev/ttyUSB0",
        firmware_type=ApplicationType.SPINEL,
        firmware_version=None,
        source="probe",
        owners=[],
    )

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.util.guess_firmware_info",
            return_value=FirmwareInfo(
                device="/dev/ttyUSB0",
                firmware_type=ApplicationType.EZSP,
                firmware_version=None,
                source="unknown",
                owners=[owner1, owner2],
            ),
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.Flasher",
            return_value=mock_flasher,
        ) as flasher_mock,
        patch(
            "homeassistant.components.homeassistant_hardware.util.parse_firmware_image"
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.probe_silabs_firmware_info",
            return_value=expected_firmware_info,
        ),
    ):
        after_flash_info = await async_flash_silabs_firmware(
            hass=hass,
            device="/dev/ttyUSB0",
            fw_data=b"firmware contents",
            expected_installed_firmware_type=ApplicationType.SPINEL,
            bootloader_reset_type=(),
            progress_callback=progress_callback,
        )

    assert progress_callback.mock_calls == [call(0, 100), call(50, 100), call(100, 100)]
    assert after_flash_info == expected_firmware_info

    # Verify Flasher was called with correct bootloader_reset parameter
    assert flasher_mock.call_count == 1
    assert flasher_mock.mock_calls[0].kwargs["bootloader_reset"] == ()

    # Both owning integrations/addons are stopped and restarted
    assert owner1.temporarily_stop.mock_calls == [
        call(hass),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aenter__(ANY),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aexit__(ANY, None, None, None),
    ]

    assert owner2.temporarily_stop.mock_calls == [
        call(hass),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aenter__(ANY),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aexit__(ANY, None, None, None),
    ]


async def test_async_flash_silabs_firmware_flash_failure(hass: HomeAssistant) -> None:
    """Test async_flash_silabs_firmware flash failure."""
    owner1 = create_mock_owner()
    owner2 = create_mock_owner()

    mock_flasher = Mock()
    mock_flasher.enter_bootloader = AsyncMock()
    mock_flasher.flash_firmware = AsyncMock(side_effect=RuntimeError("Failure!"))

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.util.guess_firmware_info",
            return_value=FirmwareInfo(
                device="/dev/ttyUSB0",
                firmware_type=ApplicationType.EZSP,
                firmware_version=None,
                source="unknown",
                owners=[owner1, owner2],
            ),
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.Flasher",
            return_value=mock_flasher,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.parse_firmware_image"
        ),
        pytest.raises(HomeAssistantError, match="Failed to flash firmware") as exc,
    ):
        await async_flash_silabs_firmware(
            hass=hass,
            device="/dev/ttyUSB0",
            fw_data=b"firmware contents",
            expected_installed_firmware_type=ApplicationType.SPINEL,
            bootloader_reset_type=None,
        )

    # Both owning integrations/addons are stopped and restarted
    assert owner1.temporarily_stop.mock_calls == [
        call(hass),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aenter__(ANY),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aexit__(ANY, HomeAssistantError, exc.value, ANY),
    ]
    assert owner2.temporarily_stop.mock_calls == [
        call(hass),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aenter__(ANY),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aexit__(ANY, HomeAssistantError, exc.value, ANY),
    ]


async def test_async_flash_silabs_firmware_probe_failure(hass: HomeAssistant) -> None:
    """Test async_flash_silabs_firmware probe failure."""
    owner1 = create_mock_owner()
    owner2 = create_mock_owner()

    mock_flasher = Mock()
    mock_flasher.enter_bootloader = AsyncMock()
    mock_flasher.flash_firmware = AsyncMock()

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.util.guess_firmware_info",
            return_value=FirmwareInfo(
                device="/dev/ttyUSB0",
                firmware_type=ApplicationType.EZSP,
                firmware_version=None,
                source="unknown",
                owners=[owner1, owner2],
            ),
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.Flasher",
            return_value=mock_flasher,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.parse_firmware_image"
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.probe_silabs_firmware_info",
            return_value=None,
        ),
        pytest.raises(
            HomeAssistantError, match="Failed to probe the firmware after flashing"
        ),
    ):
        await async_flash_silabs_firmware(
            hass=hass,
            device="/dev/ttyUSB0",
            fw_data=b"firmware contents",
            expected_installed_firmware_type=ApplicationType.SPINEL,
            bootloader_reset_type=None,
        )

    # Both owning integrations/addons are stopped and restarted
    assert owner1.temporarily_stop.mock_calls == [
        call(hass),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aenter__(ANY),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aexit__(ANY, None, None, None),
    ]
    assert owner2.temporarily_stop.mock_calls == [
        call(hass),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aenter__(ANY),
        # pylint: disable-next=unnecessary-dunder-call
        call().__aexit__(ANY, None, None, None),
    ]
