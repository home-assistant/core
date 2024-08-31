"""Tests for the diagnostics data provided by the Withings integration."""
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.withings import prepare_webhook_setup, setup_integration
from tests.typing import ClientSessionGenerator


async def test_diagnostics_polling_instance(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, polling_config_entry, False)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, polling_config_entry)
        == snapshot
    )


async def test_diagnostics_webhook_instance(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, webhook_config_entry)
    await prepare_webhook_setup(hass, freezer)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, webhook_config_entry)
        == snapshot
    )


async def test_diagnostics_cloudhook_instance(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test diagnostics."""
    with patch(
        "homeassistant.components.cloud.async_is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_connected", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value="https://hooks.nabu.casa/ABCD",
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.cloud.async_delete_cloudhook",
    ), patch(
        "homeassistant.components.withings.webhook_generate_url",
    ):
        await setup_integration(hass, webhook_config_entry)
        await prepare_webhook_setup(hass, freezer)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, webhook_config_entry)
        == snapshot
    )
