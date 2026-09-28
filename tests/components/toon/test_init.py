"""Tests for the Toon component."""

import time
from unittest.mock import patch

from toonapi import Agreement, Status
from toonapi.models import ThermostatInfo

from homeassistant.components.toon import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import MockConfigEntry


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
            "agreement_id": "test-agreement-id",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.toon.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entry_minor_version_2_2(hass: HomeAssistant) -> None:
    """Test migrating a 2.1 config entry to 2.2."""
    with patch("homeassistant.components.toon.async_setup_entry", return_value=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "auth_implementation": DOMAIN,
                "token": {
                    "refresh_token": "mock-refresh-token",
                    "access_token": "mock-access-token",
                    "type": "Bearer",
                    "expires_in": 60,
                },
                "agreement_id": 123,
            },
            version=2,
            minor_version=1,
            unique_id=123,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 2
        assert entry.minor_version == 2
        assert entry.unique_id == "123"


async def test_device_registry_via_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that child devices are linked to their parent via via_device_id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        unique_id="test-agreement-id",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time.time() + 3600,
            },
            "agreement_id": "test-agreement-id",
        },
    )
    config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            "client-id",
            "client-secret",
            "https://api.toon.eu/authorize",
            "https://api.toon.eu/token",
        ),
    )

    agreement = Agreement(
        agreement_id="test-agreement-id",
        display_common_name="display-common-name",
        display_hardware_version="qb2/ICY/v0.8",
        display_software_version="qb2/v1.2",
        heating_type="gas",
        is_toon_solar=True,
    )
    status = Status(agreement=agreement)
    status.thermostat = ThermostatInfo(have_opentherm_boiler=True)

    with (
        patch("toonapi.Toon.activate_agreement"),
        patch("toonapi.Toon.update", return_value=status),
        patch(
            "homeassistant.components.toon.coordinator."
            "ToonDataUpdateCoordinator.register_webhook"
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    def get_device(*identifier: str) -> dr.DeviceEntry:
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, *identifier),  # type: ignore[arg-type]
            config_entry.entry_id,
        )
        assert device is not None
        return device

    display = get_device("test-agreement-id")
    assert display.via_device_id is None

    meter_adapter = get_device("test-agreement-id", "meter_adapter")
    assert meter_adapter.via_device_id == display.id

    electricity = get_device("test-agreement-id", "electricity")
    assert electricity.via_device_id == meter_adapter.id

    boiler_module = get_device("test-agreement-id", "boiler_module")
    assert boiler_module.via_device_id == display.id

    assert get_device("test-agreement-id", "gas").via_device_id == electricity.id
    assert get_device("test-agreement-id", "water").via_device_id == electricity.id
    assert get_device("test-agreement-id", "solar").via_device_id == meter_adapter.id
    assert get_device("test-agreement-id", "boiler").via_device_id == boiler_module.id
