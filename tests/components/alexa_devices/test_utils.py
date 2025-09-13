"""Tests for Alexa Devices utils."""

from unittest.mock import AsyncMock

from aioamazondevices.const import SPEAKER_GROUP_FAMILY, SPEAKER_GROUP_MODEL
from aioamazondevices.exceptions import CannotConnect, CannotRetrieveData
import pytest

from homeassistant.components.alexa_devices.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .const import TEST_DEVICE_1_SN

from tests.common import MockConfigEntry

ENTITY_ID = "switch.echo_test_do_not_disturb"


@pytest.mark.parametrize(
    ("side_effect", "key", "error"),
    [
        (CannotConnect, "cannot_connect_with_error", "CannotConnect()"),
        (CannotRetrieveData, "cannot_retrieve_data_with_error", "CannotRetrieveData()"),
    ],
)
async def test_alexa_api_call_exceptions(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    key: str,
    error: str,
) -> None:
    """Test alexa_api_call decorator for exceptions."""

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF

    mock_amazon_devices_client.set_do_not_disturb.side_effect = side_effect

    # Call API
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == key
    assert exc_info.value.translation_placeholders == {"error": error}


async def test_alexa_unique_id_migration(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unique_id migration."""

    mock_config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Amazon",
        model="Echo Dot",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    entity = entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        unique_id=f"{TEST_DEVICE_1_SN}-do_not_disturb",
        device_id=device.id,
        config_entry=mock_config_entry,
        has_entity_name=True,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_entry_id == mock_config_entry.entry_id
    assert migrated_entity.unique_id == f"{TEST_DEVICE_1_SN}-dnd"


async def test_alexa_dnd_group_removal(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test dnd switch is removed for Speaker Groups."""

    mock_config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Amazon",
        model=SPEAKER_GROUP_MODEL,
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    entity = entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        unique_id=f"{TEST_DEVICE_1_SN}-do_not_disturb",
        device_id=device.id,
        config_entry=mock_config_entry,
        has_entity_name=True,
    )

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].device_family = SPEAKER_GROUP_FAMILY

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is None
