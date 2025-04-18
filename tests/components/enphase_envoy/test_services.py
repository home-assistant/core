"""Test the Enphase Envoy services."""

from unittest.mock import AsyncMock, patch

from pyenphase.const import URL_TARIFF
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import DOMAIN, Platform
from homeassistant.components.enphase_envoy.services import (
    ATTR_CONFIG_ENTRY_ID,
    RAW_SERVICE_LIST,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
    ],
    indirect=["mock_envoy"],
)
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
    for service in RAW_SERVICE_LIST:
        assert hass.services.has_service(DOMAIN, service)
    assert snapshot == list(hass.services.async_services_for_domain(DOMAIN).keys())


async def test_service_load_unload(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service loading and unlodig."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # test with unloaded config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    for service in RAW_SERVICE_LIST:
        with pytest.raises(
            ServiceValidationError,
            match=f"{service}: Enphase Envoy is not yet initialized",
        ):
            await hass.services.async_call(
                DOMAIN,
                service,
                {ATTR_CONFIG_ENTRY_ID: config_entry.entry_id},
                blocking=True,
                return_response=True,
            )

    # test with simulated second loaded envoy for COV on envoylist handling
    with (
        patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, config_entry)
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("service", "mock_envoy"),
    [
        (
            "get_raw_tariff",
            "envoy",
        ),
    ],
    indirect=["mock_envoy"],
)
async def test_service_get_raw(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test service calls for get_raw service."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # mock data has no tariff data in raw
    with pytest.raises(
        ServiceValidationError,
        match=f"{service}: this endpoint is not collected by the Envoy",
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: config_entry.entry_id},
            blocking=True,
            return_response=True,
        )

    test_pattern = {"tariff": {"currency": {"code": "EUR"}}}
    mock_envoy.data.raw = {URL_TARIFF: test_pattern}
    # add tariff data to mock raw
    result = await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_CONFIG_ENTRY_ID: config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert result["raw"] == test_pattern


@pytest.mark.parametrize(
    ("service", "mock_envoy"),
    [
        (
            "get_raw_tariff",
            "envoy",
        ),
    ],
    indirect=["mock_envoy"],
)
async def test_service_get_raw_exceptions(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test service calls for get_raw service with faulty service data."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(
        ServiceValidationError,
        match=f"No Envoy configuration entry found: {service} {'123456789'}",
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: "123456789"},
            blocking=True,
            return_response=True,
        )

    mock_envoy.data.raw = {}
    with pytest.raises(
        ServiceValidationError,
        match=f"{service}: Enphase Envoy is not yet initialized",
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: config_entry.entry_id},
            blocking=True,
            return_response=True,
        )
