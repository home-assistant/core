"""Tests for the Elgato update platform."""

from collections.abc import Callable
from unittest.mock import MagicMock

from elgato import ElgatoConnectionError, ElgatoError, FirmwareImage
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_UPDATE_PERCENTAGE,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
) -> None:
    """Test a device already running what Elgato ships.

    The device fixture reports build 192, so the catalog is pulled back to
    match it.
    """
    latest = mock_firmware_catalog.versions.return_value[53]
    mock_firmware_catalog.versions.return_value = {
        53: type(latest)(board_type=53, build_number=192, version="1.0.3")
    }
    await hass.config_entries.async_reload(
        hass.config_entries.async_entries("elgato")[0].entry_id
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF


async def test_elgato_ships_nothing_for_this_board(
    hass: HomeAssistant,
    mock_firmware_catalog: MagicMock,
) -> None:
    """Test a board Elgato publishes no firmware for.

    Nothing to compare against is not an error, it just leaves the entity
    with no opinion.
    """
    mock_firmware_catalog.versions.return_value = {}
    await hass.config_entries.async_reload(
        hass.config_entries.async_entries("elgato")[0].entry_id
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


async def test_install(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    mock_firmware_catalog: MagicMock,
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

    # Whatever happened, the entity does not stay stuck mid-install.
    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None


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
    side_effect: type[Exception],
) -> None:
    """Test Elgato's servers being unreachable.

    The light is on the local network and Elgato is not, so a bad day at
    their end costs the latest version and nothing else. The light and its
    other entities carry on.
    """
    mock_firmware_catalog.versions.side_effect = side_effect
    await hass.config_entries.async_reload(
        hass.config_entries.async_entries("elgato")[0].entry_id
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    assert (light := hass.states.get("light.frenck"))
    assert light.state != STATE_UNAVAILABLE
