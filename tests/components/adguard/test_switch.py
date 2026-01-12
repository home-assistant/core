"""Tests for the AdGuard Home switch entity."""

from collections.abc import Callable
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

from adguardhome import AdGuardHomeError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard switch platform."""
    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("switch_name", "service", "call_assertion"),
    [
        (
            "protection",
            SERVICE_TURN_ON,
            lambda mock: mock.enable_protection.assert_called_once(),
        ),
        (
            "protection",
            SERVICE_TURN_OFF,
            lambda mock: mock.disable_protection.assert_called_once(),
        ),
        (
            "parental_control",
            SERVICE_TURN_ON,
            lambda mock: mock.parental.enable.assert_called_once(),
        ),
        (
            "parental_control",
            SERVICE_TURN_OFF,
            lambda mock: mock.parental.disable.assert_called_once(),
        ),
        (
            "safe_search",
            SERVICE_TURN_ON,
            lambda mock: mock.safesearch.enable.assert_called_once(),
        ),
        (
            "safe_search",
            SERVICE_TURN_OFF,
            lambda mock: mock.safesearch.disable.assert_called_once(),
        ),
        (
            "safe_browsing",
            SERVICE_TURN_ON,
            lambda mock: mock.safebrowsing.enable.assert_called_once(),
        ),
        (
            "safe_browsing",
            SERVICE_TURN_OFF,
            lambda mock: mock.safebrowsing.disable.assert_called_once(),
        ),
        (
            "filtering",
            SERVICE_TURN_ON,
            lambda mock: mock.filtering.enable.assert_called_once(),
        ),
        (
            "filtering",
            SERVICE_TURN_OFF,
            lambda mock: mock.filtering.disable.assert_called_once(),
        ),
        (
            "query_log",
            SERVICE_TURN_ON,
            lambda mock: mock.querylog.enable.assert_called_once(),
        ),
        (
            "query_log",
            SERVICE_TURN_OFF,
            lambda mock: mock.querylog.disable.assert_called_once(),
        ),
    ],
)
async def test_switch_actions(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    switch_name: str,
    service: str,
    call_assertion: Callable[[AsyncMock], Any],
) -> None:
    """Test the adguard switch actions."""
    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    await hass.services.async_call(
        "switch",
        service,
        {ATTR_ENTITY_ID: f"switch.adguard_home_{switch_name}"},
        blocking=True,
    )

    call_assertion(mock_adguard)


@pytest.mark.parametrize(
    ("service", "expected_message"),
    [
        (
            SERVICE_TURN_ON,
            "An error occurred while turning on AdGuard Home switch",
        ),
        (
            SERVICE_TURN_OFF,
            "An error occurred while turning off AdGuard Home switch",
        ),
    ],
)
async def test_switch_action_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    service: str,
    expected_message: str,
) -> None:
    """Test the adguard switch actions."""
    caplog.set_level(logging.ERROR)

    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    mock_adguard.enable_protection.side_effect = AdGuardHomeError("Boom")
    mock_adguard.disable_protection.side_effect = AdGuardHomeError("Boom")

    await hass.services.async_call(
        "switch",
        service,
        {ATTR_ENTITY_ID: "switch.adguard_home_protection"},
        blocking=True,
    )
    assert expected_message in caplog.text
