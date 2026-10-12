"""Tests for the Elgato update platform."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from elgato import (
    ElgatoConnectionError,
    ElgatoError,
    ElgatoFirmwareError,
    FirmwareImage,
    FirmwareVersion,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.elgato import ELGATO_KEY
from homeassistant.components.elgato.const import (
    DOMAIN,
    FIRMWARE_SCAN_INTERVAL,
    SCAN_INTERVAL,
)
from homeassistant.components.elgato.update import REBOOT_TIMEOUT
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_UPDATE_PERCENTAGE,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_MAC,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "update.frenck_firmware"

pytestmark = [
    pytest.mark.parametrize("device_fixtures", ["key-light"]),
    pytest.mark.usefixtures("device_fixtures", "init_integration"),
]


async def test_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Elgato firmware update entity."""
    assert (state := hass.states.get(ENTITY_ID))
    assert state == snapshot
    assert state.state == STATE_ON

    assert (entry := entity_registry.async_get(ENTITY_ID))
    assert entry == snapshot

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot


async def test_up_to_date(
    hass: HomeAssistant,
    mock_firmware_catalog: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device already running what Elgato ships.

    The device fixture reports build 192, so the catalog is pulled back to
    match it.
    """
    mock_firmware_catalog.versions.return_value = {
        53: FirmwareVersion(board_type=53, build_number=192, version="1.0.3")
    }
    freezer.tick(FIRMWARE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF


async def test_elgato_ships_nothing_for_this_board(
    hass: HomeAssistant,
    mock_firmware_catalog: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a board Elgato publishes no firmware for.

    Nothing to compare against is not an error, it just leaves the entity
    with no opinion.
    """
    mock_firmware_catalog.versions.return_value = {}
    freezer.tick(FIRMWARE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


async def test_install(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    mock_firmware_catalog: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test installing the firmware Elgato ships."""
    reported: list[int | None] = []
    in_progress_while_downloading = None

    async def download(board_type: int) -> FirmwareImage:
        """Stand in for fetching the image off Elgato's servers."""
        nonlocal in_progress_while_downloading
        in_progress_while_downloading = hass.states.get(ENTITY_ID).attributes[
            ATTR_IN_PROGRESS
        ]
        return FirmwareImage(
            board_type=board_type,
            build_number=222,
            version="1.0.3",
            data=b"\x00" * 8192,
        )

    async def install(
        image: FirmwareImage,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Stand in for a device taking a firmware image."""
        assert on_progress is not None
        for sent in (4096, 8192):
            on_progress(sent, len(image.data))
            reported.append(
                hass.states.get(ENTITY_ID).attributes[ATTR_UPDATE_PERCENTAGE]
            )

    mock_firmware_catalog.download.side_effect = download
    mock_elgato.update_firmware.side_effect = install

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    # Fetching the image is part of the install, so the entity says so
    # before it starts rather than after.
    assert in_progress_while_downloading is True

    mock_firmware_catalog.download.assert_called_once_with(53)
    mock_elgato.update_firmware.assert_called_once()
    assert reported == [50, 100]

    # Still installing: the device took the firmware and is restarting.
    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_IN_PROGRESS] is True

    # It comes back on the build it was given.
    mock_elgato.info.return_value.firmware_build_number = 222
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.state == STATE_OFF


async def test_install_that_never_comes_back(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device that takes the firmware and never reports it.

    Without a way out, the entity would sit there saying it is installing
    for as long as Home Assistant runs.
    """
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_IN_PROGRESS] is True

    freezer.tick(timedelta(seconds=REBOOT_TIMEOUT + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_install_on_a_device_that_stays_away(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device that takes the firmware and never answers again.

    It does not sit there claiming to install. An entity whose device is
    gone is unavailable, and that is what it says.
    """
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_elgato.state.side_effect = ElgatoConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_a_second_install_is_turned_away(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
) -> None:
    """Test two installs at once do not both reach the device."""

    async def slow(image: FirmwareImage, **kwargs: Any) -> None:
        """Take long enough for the second call to arrive."""
        await asyncio.sleep(0)

    mock_elgato.update_firmware.side_effect = slow

    results = await asyncio.gather(
        *[
            hass.services.async_call(
                UPDATE_DOMAIN,
                SERVICE_INSTALL,
                {ATTR_ENTITY_ID: ENTITY_ID},
                blocking=True,
            )
            for _ in range(2)
        ],
        return_exceptions=True,
    )

    assert sum(isinstance(result, HomeAssistantError) for result in results) == 1
    assert mock_elgato.update_firmware.call_count == 1


async def test_catalog_refresh_during_an_install(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    mock_firmware_catalog: MagicMock,
) -> None:
    """Test the catalog refreshing while an install is running.

    What Elgato ships says nothing about whether this device is done, so a
    refresh in the middle must not report the install as finished.
    """

    async def install(image: FirmwareImage, **kwargs: Any) -> None:
        """Let Elgato publish something while the device is busy."""
        await hass.data[ELGATO_KEY].async_refresh()
        await hass.async_block_till_done()

        assert (state := hass.states.get(ENTITY_ID))
        assert state.attributes[ATTR_IN_PROGRESS] is True

    mock_elgato.update_firmware.side_effect = install

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert mock_elgato.update_firmware.call_count == 1


async def test_download_does_not_hold_the_device(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    mock_firmware_catalog: MagicMock,
) -> None:
    """Test fetching the image leaves the device free.

    Downloading talks to Elgato. If it held the device lock, a slow or
    unreachable Elgato would park every light command behind it for the
    length of their timeout.
    """
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    locked_while_downloading = None
    locked_while_uploading = None

    async def download(board_type: int) -> FirmwareImage:
        nonlocal locked_while_downloading
        locked_while_downloading = coordinator.device_lock.locked()
        return FirmwareImage(
            board_type=board_type,
            build_number=222,
            version="1.0.3",
            data=b"\x00" * 8192,
        )

    async def install(image: FirmwareImage, **kwargs: Any) -> None:
        nonlocal locked_while_uploading
        locked_while_uploading = coordinator.device_lock.locked()

    mock_firmware_catalog.download.side_effect = download
    mock_elgato.update_firmware.side_effect = install

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert locked_while_downloading is False
    assert locked_while_uploading is True


async def test_device_page_follows_the_firmware(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_elgato: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the device page shows the firmware after an install.

    DeviceInfo is read when an entity is added and not again, so the version
    someone reads right after installing would otherwise be the old one.
    """
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "CN11A1A00001"),
        hass.config_entries.async_entries(DOMAIN)[0].entry_id,
    )
    assert device is not None
    assert device.sw_version == "1.0.3 (192)"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_elgato.info.return_value.firmware_build_number = 222
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "CN11A1A00001"),
        hass.config_entries.async_entries(DOMAIN)[0].entry_id,
    )
    assert device is not None
    assert device.sw_version == "1.0.3 (222)"


async def test_install_error(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
) -> None:
    """Test a device refusing the firmware it was handed."""
    mock_elgato.update_firmware.side_effect = ElgatoError

    with pytest.raises(
        HomeAssistantError,
        match="An unknown error occurred while communicating with the Elgato device",
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize(
    "side_effect",
    [ElgatoConnectionError, ElgatoError],
)
async def test_elgato_unreachable(
    hass: HomeAssistant,
    mock_firmware_catalog: MagicMock,
    freezer: FrozenDateTimeFactory,
    side_effect: type[Exception],
) -> None:
    """Test Elgato's servers being unreachable.

    The light is on the local network and Elgato is not, so a bad day at
    their end costs the latest version and nothing else. The light and its
    other entities carry on.
    """
    mock_firmware_catalog.versions.side_effect = side_effect
    freezer.tick(FIRMWARE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    assert (light := hass.states.get("light.frenck"))
    assert light.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("side_effect", "message", "still_reachable"),
    [
        (
            ElgatoConnectionError,
            "An error occurred while downloading the firmware from Elgato",
            False,
        ),
        (
            ElgatoFirmwareError,
            "An unknown error occurred while downloading the firmware from Elgato",
            True,
        ),
    ],
)
async def test_download_failure_leaves_the_light_alone(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    mock_firmware_catalog: MagicMock,
    side_effect: type[Exception],
    message: str,
    still_reachable: bool,
) -> None:
    """Test Elgato failing to hand over the image.

    Only reaching Elgato says anything about this entity; an image that
    arrives and fails to verify means Elgato answered, just badly.
    """
    mock_firmware_catalog.download.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_elgato.update_firmware.assert_not_called()

    assert (light := hass.states.get("light.frenck"))
    assert light.state != STATE_UNAVAILABLE

    assert (state := hass.states.get(ENTITY_ID))
    assert (state.state != STATE_UNAVAILABLE) is still_reachable


async def test_install_rejected_by_the_device(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
) -> None:
    """Test a device turning the firmware away for a reason worth reading."""
    mock_elgato.update_firmware.side_effect = ElgatoFirmwareError(
        "Battery is at 11%, connect the device to power before updating its firmware"
    )

    with pytest.raises(HomeAssistantError, match="Battery is at 11%"):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


async def test_install_keeps_the_device_to_itself(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
) -> None:
    """Test a poll cannot land in the middle of an install.

    A device stops answering while it erases a flash slot, and enough traffic
    during that window takes its HTTP server down and restarts the light.
    """
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    refresh: asyncio.Task[None] | None = None
    polls_during_install = 0

    async def install(image: FirmwareImage, **kwargs: Any) -> None:
        """Ask for a refresh while the device is busy taking firmware."""
        nonlocal refresh, polls_during_install
        before = mock_elgato.state.call_count
        refresh = hass.async_create_task(coordinator.async_refresh())
        for _ in range(5):
            await asyncio.sleep(0)
        polls_during_install = mock_elgato.state.call_count - before

    mock_elgato.update_firmware.side_effect = install
    polls_before = mock_elgato.state.call_count

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert refresh is not None
    await refresh

    assert polls_during_install == 0
    # And it is not blocked forever; the poll lands once the install is done.
    assert mock_elgato.state.call_count > polls_before


async def test_manual_update_check(
    hass: HomeAssistant,
    mock_firmware_catalog: MagicMock,
) -> None:
    """Test asking for an update check reaches Elgato.

    The device coordinator knows what the light runs; only the catalog knows
    what Elgato ships, and that is the half being asked about.
    """
    await async_setup_component(hass, HA_DOMAIN, {})
    checks_before = mock_firmware_catalog.versions.call_count

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert mock_firmware_catalog.versions.call_count > checks_before


async def test_install_keeps_the_device_from_everyone(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
) -> None:
    """Test a light command cannot land in the middle of an install either.

    Polling is not the only thing that talks to the device; every button,
    switch and light action does too.
    """
    turn_on: asyncio.Task[None] | None = None
    commands_during_install = 0

    async def install(image: FirmwareImage, **kwargs: Any) -> None:
        """Ask the light to turn on while the device is taking firmware."""
        nonlocal turn_on, commands_during_install
        before = mock_elgato.light.call_count
        turn_on = hass.async_create_task(
            hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: "light.frenck"},
                blocking=True,
            )
        )
        for _ in range(5):
            await asyncio.sleep(0)
        commands_during_install = mock_elgato.light.call_count - before

    mock_elgato.update_firmware.side_effect = install

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert turn_on is not None
    await turn_on

    assert commands_during_install == 0
    assert mock_elgato.light.call_count == 1


async def test_one_catalog_for_every_device(
    hass: HomeAssistant,
    mock_firmware_catalog: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a second device does not fetch the catalog all over again.

    Elgato publishes one catalog covering every model, so it is read once
    and shared, not once per config entry.
    """
    calls_for_one_device = mock_firmware_catalog.versions.call_count

    second = MockConfigEntry(
        title="CN11A1A00002",
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.2", CONF_MAC: "AA:BB:CC:DD:EE:00"},
        unique_id="CN11A1A00002",
    )
    second.add_to_hass(hass)
    await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    assert mock_firmware_catalog.versions.call_count == calls_for_one_device
