"""Test the my-PV button platform."""

from unittest.mock import AsyncMock, patch

from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_my_pv_client")
async def test_button(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of a button platform."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.BUTTON]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_button_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a button is unavailable when not connected."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.BUTTON]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.connected = False

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("button.my_pv_ac_elwa_2_restart")
    assert state.state == STATE_UNAVAILABLE


async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test successful press of a button."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.BUTTON]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {"entity_id": "button.my_pv_ac_elwa_2_restart"},
        blocking=True,
    )
    mock_my_pv_client.send_command.assert_awaited_once_with("reboot_device", None)


async def test_button_press_send_command_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for HomeAssistantError when send_command returns False."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.BUTTON]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.send_command.return_value = False
    with (
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {"entity_id": "button.my_pv_ac_elwa_2_restart"},
            blocking=True,
        )
    mock_my_pv_client.send_command.assert_awaited_once_with("reboot_device", None)

    mock_my_pv_client.send_command.reset_mock()
    mock_my_pv_client.send_command.return_value = True
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {"entity_id": "button.my_pv_ac_elwa_2_restart"},
        blocking=True,
    )
    mock_my_pv_client.send_command.assert_awaited_once_with("reboot_device", None)


@pytest.mark.parametrize(
    ("error", "expected_ha_error"),
    [
        (MyPVConnectionError(), HomeAssistantError),
        (MyPVAuthenticationError(), ConfigEntryAuthFailed),
    ],
)
async def test_button_press_send_command_throws_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    error: MyPVConnectionError | MyPVAuthenticationError,
    expected_ha_error: type[HomeAssistantError],
) -> None:
    """Test for HomeAssistantError when send_command throws error."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.BUTTON]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_my_pv_client.send_command.side_effect = error
    with (
        pytest.raises(expected_ha_error),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {"entity_id": "button.my_pv_ac_elwa_2_restart"},
            blocking=True,
        )
    mock_my_pv_client.send_command.assert_awaited_once_with("reboot_device", None)

    mock_my_pv_client.send_command.reset_mock()
    mock_my_pv_client.send_command.side_effect = None
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {"entity_id": "button.my_pv_ac_elwa_2_restart"},
        blocking=True,
    )
    mock_my_pv_client.send_command.assert_awaited_once_with("reboot_device", None)
