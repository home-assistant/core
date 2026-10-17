"""Tests for the number platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.vesync.number import _warm_mist_humidifier
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import (
    ALL_DEVICE_NAMES,
    ENTITY_HUMIDIFIER_600S_WARM_MIST_LEVEL,
    ENTITY_HUMIDIFIER_MIST_LEVEL,
    mock_devices_response,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_number_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    mock_devices_response(aioclient_mock, device_name)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == NUMBER_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


async def test_set_mist_level_bad_range(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test set_mist_level invalid value."""
    with (
        pytest.raises(ServiceValidationError),
        patch(
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_mist_level",
            return_value=True,
        ) as method_mock,
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_MIST_LEVEL, ATTR_VALUE: "10"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_not_called()


async def test_set_mist_level(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test set_mist_level usage."""

    with patch(
        "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_mist_level",
        return_value=True,
    ) as method_mock:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_MIST_LEVEL, ATTR_VALUE: "3"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_called_once()


async def test_mist_level(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the state of mist_level number entity."""

    assert hass.states.get(ENTITY_HUMIDIFIER_MIST_LEVEL).state == "6"


async def test_warm_mist_level(
    hass: HomeAssistant, humidifier_600s_config_entry: MockConfigEntry
) -> None:
    """Test the state of warm_mist_level number entity."""

    state = hass.states.get(ENTITY_HUMIDIFIER_600S_WARM_MIST_LEVEL)
    assert state.state == "2"
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 3


async def test_set_warm_mist_level(
    hass: HomeAssistant, humidifier_600s_config_entry: MockConfigEntry
) -> None:
    """Test set_warm_level usage."""

    with patch(
        "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_warm_level",
        return_value=True,
    ) as method_mock:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_600S_WARM_MIST_LEVEL, ATTR_VALUE: "3"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_called_once_with(3)


async def test_set_warm_mist_level_bad_range(
    hass: HomeAssistant, humidifier_600s_config_entry: MockConfigEntry
) -> None:
    """Test set_warm_level invalid value."""
    with (
        pytest.raises(ServiceValidationError),
        patch(
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_warm_level",
            return_value=True,
        ) as method_mock,
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_600S_WARM_MIST_LEVEL, ATTR_VALUE: "4"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_not_called()


async def test_set_warm_mist_level_raises_error(
    hass: HomeAssistant, humidifier_600s_config_entry: MockConfigEntry
) -> None:
    """Test set_warm_level raises HomeAssistantError when the device rejects it."""
    with (
        pytest.raises(HomeAssistantError),
        patch(
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_warm_level",
            return_value=False,
        ),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_600S_WARM_MIST_LEVEL, ATTR_VALUE: "1"},
            blocking=True,
        )


async def test_warm_mist_humidifier_rejects_unsupported_device(fan) -> None:
    """Test the warm mist guard raises for devices without warm mist."""
    with pytest.raises(HomeAssistantError):
        _warm_mist_humidifier(fan)
