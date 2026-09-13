"""Test the my-PV update platform."""

from unittest.mock import AsyncMock, patch

from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_my_pv_client")
async def test_update_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of a update platform."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.UPDATE]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_my_pv_client")
async def test_update_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of a update platform."""

    mock_my_pv_client.latest_firmware_version = "e0002201"
    mock_my_pv_client.firmware_update_available = True

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.UPDATE]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a update is unavailable when not connected."""

    mock_my_pv_client.latest_firmware_version = "e0002201"
    mock_my_pv_client.firmware_update_available = True

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.UPDATE]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.connected = False

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("update.my_pv_ac_elwa_2_firmware")
    assert state.state == STATE_UNAVAILABLE


async def test_update_install(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test successful press of a update."""

    mock_my_pv_client.latest_firmware_version = "e0002201"
    mock_my_pv_client.firmware_update_available = True

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.UPDATE]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {"entity_id": "update.my_pv_ac_elwa_2_firmware"},
        blocking=True,
    )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()


async def test_update_press_update_firmware_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for HomeAssistantError when update_firmware returns False."""

    mock_my_pv_client.latest_firmware_version = "e0002201"
    mock_my_pv_client.firmware_update_available = True

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.UPDATE]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.update_firmware.return_value = False
    with (
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {"entity_id": "update.my_pv_ac_elwa_2_firmware"},
            blocking=True,
        )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()

    mock_my_pv_client.update_firmware.reset_mock()
    mock_my_pv_client.update_firmware.return_value = True
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {"entity_id": "update.my_pv_ac_elwa_2_firmware"},
        blocking=True,
    )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("error", "expected_ha_error"),
    [
        (MyPVConnectionError(), HomeAssistantError),
        (MyPVAuthenticationError(), ConfigEntryAuthFailed),
    ],
)
async def test_update_press_update_firmware_throws_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    error: MyPVConnectionError | MyPVAuthenticationError,
    expected_ha_error: type[HomeAssistantError],
) -> None:
    """Test for HomeAssistantError when update_firmware throws error."""

    mock_my_pv_client.latest_firmware_version = "e0002201"
    mock_my_pv_client.firmware_update_available = True

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.UPDATE]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.update_firmware.side_effect = error
    with (
        pytest.raises(expected_ha_error),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {"entity_id": "update.my_pv_ac_elwa_2_firmware"},
            blocking=True,
        )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()

    mock_my_pv_client.update_firmware.reset_mock()
    mock_my_pv_client.update_firmware.side_effect = None
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {"entity_id": "update.my_pv_ac_elwa_2_firmware"},
        blocking=True,
    )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()
