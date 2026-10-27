"""Test the my-PV update platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from my_pv.exceptions import (
    MyPVAuthenticationError,
    MyPVConnectionError,
    MyPVTooManyRequestsError,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.my_pv.coordinator import UPDATE_INTERVAL
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
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


@pytest.fixture
def mock_my_pv_client(mock_my_pv_client: AsyncMock) -> AsyncMock:
    """Return a client with firmware update available."""
    mock_my_pv_client.latest_firmware_version = "e0002201"
    mock_my_pv_client.firmware_update_available = True
    return mock_my_pv_client


async def test_update_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of an update platform when no newer firmware is available."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.UPDATE]):
        mock_my_pv_client.latest_firmware_version = "e0002200"
        mock_my_pv_client.firmware_update_available = False

        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_my_pv_client")
async def test_update_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of an update platform when newer firmware is available."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if an update is unavailable when not connected."""
    mock_my_pv_client.connected = False

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("update.my_pv_ac_elwa_2_firmware")
    assert state.state == STATE_UNAVAILABLE


async def test_update_install(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a successful firmware update with progress."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.my_pv_ac_elwa_2_firmware"},
        blocking=True,
    )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()

    state = hass.states.get("update.my_pv_ac_elwa_2_firmware")
    assert state.state == STATE_ON
    assert not state.attributes.get(ATTR_IN_PROGRESS)
    assert state.attributes.get(ATTR_UPDATE_PERCENTAGE) is None

    mock_my_pv_client.firmware_update_progress = 0

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.my_pv_ac_elwa_2_firmware")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_IN_PROGRESS)
    assert state.attributes.get(ATTR_UPDATE_PERCENTAGE) == 0

    mock_my_pv_client.firmware_update_progress = 50

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.my_pv_ac_elwa_2_firmware")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_IN_PROGRESS)
    assert state.attributes.get(ATTR_UPDATE_PERCENTAGE) == 50

    mock_my_pv_client.firmware_version = "e0002201"
    mock_my_pv_client.firmware_update_available = False
    mock_my_pv_client.firmware_update_progress = None

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.my_pv_ac_elwa_2_firmware")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_IN_PROGRESS)
    assert state.attributes.get(ATTR_UPDATE_PERCENTAGE) is None


async def test_update_in_progress_on_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test a firmware update that is already in progress when the entity is added."""
    mock_my_pv_client.firmware_update_progress = 40

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("update.my_pv_ac_elwa_2_firmware")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_IN_PROGRESS)
    assert state.attributes.get(ATTR_UPDATE_PERCENTAGE) == 40

    # A second install is rejected while the update is in progress
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.my_pv_ac_elwa_2_firmware"},
            blocking=True,
        )
    mock_my_pv_client.update_firmware.assert_not_awaited()


async def test_update_install_firmware_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for HomeAssistantError when update_firmware returns False."""
    await setup_integration(hass, mock_config_entry)

    mock_my_pv_client.update_firmware.return_value = False
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.my_pv_ac_elwa_2_firmware"},
            blocking=True,
        )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()

    mock_my_pv_client.update_firmware.reset_mock()
    mock_my_pv_client.update_firmware.return_value = True
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.my_pv_ac_elwa_2_firmware"},
        blocking=True,
    )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("error", "expected_ha_error"),
    [
        (MyPVConnectionError(), HomeAssistantError),
        (MyPVAuthenticationError(), ConfigEntryAuthFailed),
        (MyPVTooManyRequestsError(), HomeAssistantError),
    ],
)
async def test_update_install_firmware_raises_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    error: MyPVConnectionError | MyPVAuthenticationError,
    expected_ha_error: type[HomeAssistantError],
) -> None:
    """Test for HomeAssistantError when update_firmware raises an error."""
    await setup_integration(hass, mock_config_entry)

    mock_my_pv_client.update_firmware.side_effect = error
    with pytest.raises(expected_ha_error):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.my_pv_ac_elwa_2_firmware"},
            blocking=True,
        )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()

    mock_my_pv_client.update_firmware.reset_mock()
    mock_my_pv_client.update_firmware.side_effect = None
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.my_pv_ac_elwa_2_firmware"},
        blocking=True,
    )
    mock_my_pv_client.update_firmware.assert_awaited_once_with()
