"""Tests for the Alexa Devices select platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.components.alexa_devices.select import (
    SERVICE_SELECTS,
    AmazonSelectServiceEntity,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_DEVICE_1, TEST_DEVICE_1_SN, TEST_DEVICE_2, TEST_DEVICE_2_SN

from tests.common import (
    MockConfigEntry,
    State,
    async_fire_time_changed,
    mock_restore_cache,
    snapshot_platform,
)

ENTITY_ID = "select.echo_test_drop_in"
ENTITY_ID_2 = "select.fake_email_gmail_com_default_device"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_dropin_option(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a drop-in option."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "all"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "home"},
        blocking=True,
    )

    assert mock_amazon_devices_client.set_dropin_status.call_count == 1

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "home"

    device_data = deepcopy(TEST_DEVICE_1)
    device_data.communication_settings = {
        "announcements": "ON",
        "communications": "ON",
        "dropin": "Off",
    }
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: device_data
    }

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "off"},
        blocking=True,
    )

    assert mock_amazon_devices_client.set_dropin_status.call_count == 2
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "off"


async def test_offline_device(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test offline device handling."""
    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = False

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_service_select_option(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a device option."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: deepcopy(TEST_DEVICE_1),
        TEST_DEVICE_2_SN: deepcopy(TEST_DEVICE_2),
    }
    mock_amazon_devices_client.default_device = deepcopy(TEST_DEVICE_1)

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID_2))
    assert state.state == TEST_DEVICE_1.account_name

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID_2, ATTR_OPTION: TEST_DEVICE_2.account_name},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID_2))
    assert state.state == TEST_DEVICE_2.account_name
    assert (
        mock_amazon_devices_client.default_device.account_name
        == TEST_DEVICE_2.account_name
    )


async def test_service_select_option_state_persists_after_coordinator_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that selected option does not revert after a coordinator refresh."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: deepcopy(TEST_DEVICE_1),
        TEST_DEVICE_2_SN: deepcopy(TEST_DEVICE_2),
    }
    mock_amazon_devices_client.default_device = deepcopy(TEST_DEVICE_1)

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID_2, ATTR_OPTION: TEST_DEVICE_2.account_name},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID_2))
    assert state.state == TEST_DEVICE_2.account_name

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID_2))
    assert state.state == TEST_DEVICE_2.account_name


async def test_service_select_option_not_found(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that selecting an unknown device raises ServiceValidationError."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID_2, ATTR_OPTION: "Nonexistent Device"},
            blocking=True,
        )


async def test_service_select_entity_invalid_option_raises_home_assistant_error() -> (
    None
):
    """Test invalid option handling in the entity method."""
    coordinator = Mock(
        config_entry=Mock(unique_id="amzn1.account.fake_user_id"),
        data={TEST_DEVICE_1_SN: deepcopy(TEST_DEVICE_1)},
        api=Mock(default_device=deepcopy(TEST_DEVICE_1)),
    )
    entity = AmazonSelectServiceEntity(coordinator, SERVICE_SELECTS[0])

    with pytest.raises(HomeAssistantError) as excinfo:
        await entity.async_select_option("Nonexistent Device")

    assert excinfo.value.translation_key == "select_option_not_found"
    assert excinfo.value.translation_placeholders == {"option": "Nonexistent Device"}


async def test_service_select_restore_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that last known option is restored on startup."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: deepcopy(TEST_DEVICE_1),
        TEST_DEVICE_2_SN: deepcopy(TEST_DEVICE_2),
    }
    mock_amazon_devices_client.default_device = deepcopy(TEST_DEVICE_1)

    mock_restore_cache(hass, (State(ENTITY_ID_2, TEST_DEVICE_2.account_name),))

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID_2))
    assert state.state == TEST_DEVICE_2.account_name
    assert (
        mock_amazon_devices_client.default_device.account_name
        == TEST_DEVICE_2.account_name
    )


async def test_service_select_restore_state_unknown_option_ignored(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a restored state with an unknown option is ignored."""
    mock_restore_cache(hass, (State(ENTITY_ID_2, "Nonexistent Device"),))

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID_2))
    assert state.state == TEST_DEVICE_1.account_name
