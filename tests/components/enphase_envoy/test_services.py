"""Test the Enphase Envoy services."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import DOMAIN, Platform
from homeassistant.components.enphase_envoy.services import (
    ACTION_COORDINATORS,
    ACTION_TOKEN_LIFETIME,
    ATTR_ENVOY_DEVICE_ID,
    setup_envoy_service_actions,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_has_services(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the existence of the Enphase Envoy Services."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, ACTION_TOKEN_LIFETIME)
    assert snapshot == list(hass.services.async_services_for_domain(DOMAIN).keys())


async def test_service_load_unload(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service loading and unloading."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # test with unloaded config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    with pytest.raises(ServiceValidationError, match=("No Envoy found")):
        await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            {},
            blocking=True,
            return_response=True,
        )

    # test with simulated second loaded envoy for COV on envoy_coordinators_list handling
    with (
        patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]),
        patch.dict(
            hass.data[DOMAIN][ACTION_COORDINATORS], {"4321": "hello world"}, clear=True
        ),
    ):
        await setup_integration(hass, config_entry)
        assert config_entry.state is ConfigEntryState.LOADED

        # existing envoy_coordinators_list entry for COV of return in service setup
        setup_envoy_service_actions(hass)

        # existing envoy_coordinators_list entry for COV of return in service unload.
        await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_service_token_lifetime_value(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test token_lifetime service action for data return."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_TOKEN_LIFETIME,
        blocking=True,
        return_response=True,
    )
    assert result["lifetime"] == 199


async def test_service_uninitialized(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action for envoy not initialized."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    mock_envoy.data = None

    with pytest.raises(
        HomeAssistantError,
        match="Enphase Envoy is not yet initialized",
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            blocking=True,
            return_response=True,
        )


async def test_service_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action with optional device_id specified."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    entity_reg = er.async_get(hass)
    device_id = entity_reg.async_get(
        "sensor.envoy_1234_lifetime_energy_production"
    ).device_id

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_TOKEN_LIFETIME,
        {ATTR_ENVOY_DEVICE_ID: device_id},
        blocking=True,
        return_response=True,
    )
    assert result["lifetime"] == 199


async def test_service_device_id_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action for wrong device_id specified."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    device_id = "some-bogus-device-id"

    with pytest.raises(
        ServiceValidationError,
        match="No Envoy found",
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            {ATTR_ENVOY_DEVICE_ID: device_id},
            blocking=True,
            return_response=True,
        )


async def test_service_via_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action with child device id specified."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    entity_reg = er.async_get(hass)
    device_id = entity_reg.async_get("sensor.inverter_1").device_id

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_TOKEN_LIFETIME,
        {ATTR_ENVOY_DEVICE_ID: device_id},
        blocking=True,
        return_response=True,
    )
    assert result["lifetime"] == 199


async def test_service_dual_envoy_with_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action with device_id specified and multiple envoys."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    entity_reg = er.async_get(hass)
    device_id = entity_reg.async_get("sensor.inverter_1").device_id

    # dual envoy with device_id should work and find correct coordinator
    with (
        patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]),
        patch.dict(
            hass.data[DOMAIN][ACTION_COORDINATORS],
            {"4321": "hello world"},
        ),
    ):
        result = await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            {ATTR_ENVOY_DEVICE_ID: device_id},
            blocking=True,
            return_response=True,
        )

        assert result["lifetime"] == 199


async def test_service_dual_envoy_no_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action with no device_id specified and multiple envoys."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # dual envoy with no device_id should raise
    with (
        patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]),
        patch.dict(
            hass.data[DOMAIN][ACTION_COORDINATORS],
            {"4321": "hello world"},
        ),
        pytest.raises(
            ServiceValidationError,
            match="No Envoy found",
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            blocking=True,
            return_response=True,
        )
