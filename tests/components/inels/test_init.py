"""Tests for iNELS integration."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.config_entries import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import HA_INELS_PATH
from .common import DOMAIN, inels
from .conftest import setup_inels_test_integration
from .test_config_flow import default_config  # noqa: F401

from tests.common import MockConfigEntry


async def test_remove_devices_with_no_entities(hass: HomeAssistant, mock_mqtt) -> None:
    """Test that devices with no entities are removed."""
    await setup_inels_test_integration(hass)

    config_entry = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.domain == DOMAIN
    )

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "device_1")},
        name="Device_with_entity",
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "device_2")},
        name="Device_to_be_removed",
    )

    # Add an entity for device_1 but not for device_2
    entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="entity_1",
        config_entry=config_entry,
        device_id=device_1.id,
    )

    with patch.object(
        device_registry, "async_remove_device", new_callable=Mock
    ) as mock_remove_device:
        await inels.async_remove_devices_with_no_entities(hass, config_entry)

        assert mock_remove_device.call_count == 1
        mock_remove_device.assert_called_with(device_id=device_2.id)


async def test_remove_old_entities(hass: HomeAssistant, mock_mqtt) -> None:
    """Test that old entities are removed."""
    await setup_inels_test_integration(hass)

    config_entry = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.domain == DOMAIN
    )

    inels_data = inels.InelsData(mqtt=mock_mqtt)
    inels_data.old_entities = {
        "sensor": ["sensor.old_entity_1"],
        "light": ["light.old_entity_2"],
    }
    config_entry.runtime_data = inels_data

    entity_registry = er.async_get(hass)

    # Add old entities to the entity registry
    entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="old_entity_1",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        domain="light",
        platform=DOMAIN,
        unique_id="old_entity_2",
        config_entry=config_entry,
    )

    with patch.object(
        entity_registry, "async_remove", new_callable=Mock
    ) as mock_remove_entity:
        await inels.async_remove_old_entities(hass, config_entry)

        # Ensure all pending tasks are completed
        await hass.async_block_till_done()

        # Verify that old entities were removed
        assert mock_remove_entity.call_count == 2
        mock_remove_entity.assert_any_call("sensor.old_entity_1")
        mock_remove_entity.assert_any_call("light.old_entity_2")


@pytest.mark.parametrize(
    ("error_code", "expected_exception", "expected_result"),
    [
        (4, ConfigEntryAuthFailed, None),
        (3, ConfigEntryNotReady, None),
        (6, None, False),
    ],
)
async def test_connection(
    hass: HomeAssistant,
    error_code,
    expected_exception,
    expected_result,
    default_config,  # noqa: F811
) -> None:
    """Test async_setup_entry with various connection scenarios."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=default_config)
    config_entry.add_to_hass(hass)

    with patch(f"{HA_INELS_PATH}.InelsMqtt.test_connection", return_value=error_code):
        if expected_exception:
            with pytest.raises(expected_exception):
                await inels.async_setup_entry(hass, config_entry)
        else:
            result = await inels.async_setup_entry(hass, config_entry)
            assert result is expected_result
