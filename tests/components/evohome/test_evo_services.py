"""The tests for the native services of Evohome."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from evohomeasync2 import EvohomeClient
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.evohome.const import (
    ATTR_DURATION,
    ATTR_PERIOD,
    ATTR_SETPOINT,
    DOMAIN,
    EvoService,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE
from homeassistant.core import HomeAssistant

from .conftest import mock_make_request, mock_post_request, setup_evohome
from .const import TEST_INSTALLS

from tests.common import MockConfigEntry


async def test_refresh_system(
    hass: HomeAssistant,
    evohome: EvohomeClient,
) -> None:
    """Test Evohome's refresh_system service (for all temperature control systems)."""

    # EvoService.REFRESH_SYSTEM
    with patch("evohomeasync2.location.Location.update") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.REFRESH_SYSTEM,
            {},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


async def test_reset_system(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test Evohome's reset_system service (for a temperature control system)."""

    # EvoService.RESET_SYSTEM (if SZ_AUTO_WITH_RESET in modes)
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.RESET_SYSTEM,
            {},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with("AutoWithReset", until=None)


async def test_set_system_mode(
    hass: HomeAssistant,
    ctl_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Evohome's set_system_mode service (for a temperature control system)."""

    # EvoService.SET_SYSTEM_MODE: Auto
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Auto",
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with("Auto", until=None)

    freezer.move_to("2024-07-10T12:00:00+00:00")

    # EvoService.SET_SYSTEM_MODE: AutoWithEco, hours=12
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "AutoWithEco",
                ATTR_DURATION: {"hours": 12},
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(
            "AutoWithEco", until=datetime(2024, 7, 11, 0, 0, tzinfo=UTC)
        )

    # EvoService.SET_SYSTEM_MODE: Away, days=7
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Away",
                ATTR_PERIOD: {"days": 7},
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(
            "Away", until=datetime(2024, 7, 16, 23, 0, tzinfo=UTC)
        )


async def test_clear_zone_override(
    hass: HomeAssistant,
    zone_id: str,
) -> None:
    """Test Evohome's clear_zone_override service (for a heating zone)."""

    # EvoZoneMode.FOLLOW_SCHEDULE
    with patch("evohomeasync2.zone.Zone.reset") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.RESET_ZONE_OVERRIDE,
            {
                ATTR_ENTITY_ID: zone_id,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


async def test_set_zone_override(
    hass: HomeAssistant,
    zone_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Evohome's set_zone_override service (for a heating zone)."""

    freezer.move_to("2024-07-10T12:00:00+00:00")

    # EvoZoneMode.PERMANENT_OVERRIDE
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_ZONE_OVERRIDE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_SETPOINT: 19.5,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(19.5, until=None)

    # EvoZoneMode.TEMPORARY_OVERRIDE
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_ZONE_OVERRIDE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_SETPOINT: 19.5,
                ATTR_DURATION: {"minutes": 135},
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(
            19.5, until=datetime(2024, 7, 10, 14, 15, tzinfo=UTC)
        )


@pytest.mark.parametrize("install", [*TEST_INSTALLS, "botched"])
async def test_setup(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test services after setup of evohome.

    Registered services vary by the type of system.
    """

    assert hass.services.async_services_for_domain(DOMAIN).keys() == snapshot

    async for _ in setup_evohome(hass, config, install=install):
        pass

    assert hass.services.async_services_for_domain(DOMAIN).keys() == snapshot


@pytest.mark.parametrize("install", [*TEST_INSTALLS, "botched"])
async def test_load_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    install: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test load and unload config entry.

    Registered services vary by the type of system.
    """

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request(install),
        ),
        patch("evohome.auth.AbstractAuth._make_request", mock_make_request(install)),
    ):
        config_entry.add_to_hass(hass)

        assert hass.services.async_services_for_domain(DOMAIN).keys() == snapshot

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        assert hass.services.async_services_for_domain(DOMAIN).keys() == snapshot

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]

        assert hass.services.async_services_for_domain(DOMAIN).keys() == snapshot
