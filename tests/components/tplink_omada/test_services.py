"""Tests for TP-Link Omada integration services."""

from unittest.mock import MagicMock

import pytest
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.device_tracker import (
    SERVICE_BLOCK,
    SERVICE_RECONNECT,
    SERVICE_RECONNECT_CLIENT,
    SERVICE_UNBLOCK,
    async_setup_services,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)

from tests.common import MockConfigEntry, MockUser

MAC = "AA:BB:CC:DD:EE:FF"

SERVICE_ACTIONS = (
    pytest.param(
        SERVICE_RECONNECT_CLIENT, "reconnect_client", "reconnect", id="legacy"
    ),
    pytest.param(SERVICE_RECONNECT, "reconnect_client", "reconnect", id="reconnect"),
    pytest.param(SERVICE_BLOCK, "block_client", "block", id="block"),
    pytest.param(SERVICE_UNBLOCK, "unblock_client", "unblock", id="unblock"),
)

SERVICES = (
    SERVICE_RECONNECT_CLIENT,
    SERVICE_RECONNECT,
    SERVICE_BLOCK,
    SERVICE_UNBLOCK,
)

SERVICE_PARAMS = (
    pytest.param(SERVICE_RECONNECT_CLIENT, id="legacy"),
    pytest.param(SERVICE_RECONNECT, id="reconnect"),
    pytest.param(SERVICE_BLOCK, id="block"),
    pytest.param(SERVICE_UNBLOCK, id="unblock"),
)

SERVICE_METHODS = (
    pytest.param(SERVICE_RECONNECT_CLIENT, "reconnect_client", id="legacy"),
    pytest.param(SERVICE_RECONNECT, "reconnect_client", id="reconnect"),
    pytest.param(SERVICE_BLOCK, "block_client", id="block"),
    pytest.param(SERVICE_UNBLOCK, "unblock_client", id="unblock"),
)


async def test_services_registered_without_config_entries(hass: HomeAssistant) -> None:
    """Test all services register before a controller is configured."""
    async_setup_services(hass)

    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize("service", SERVICE_PARAMS)
async def test_service_no_config_entries(
    hass: HomeAssistant,
    service: str,
) -> None:
    """Test a raw-MAC service raises when no controller is configured."""
    async_setup_services(hass)

    with pytest.raises(
        ServiceValidationError, match="No active TP-Link Omada controllers found"
    ):
        await hass.services.async_call(DOMAIN, service, {"mac": MAC}, blocking=True)


@pytest.mark.parametrize(("service", "method"), SERVICE_METHODS)
async def test_service_client_action(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Test client actions use raw MAC input and an explicit controller."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        service,
        {"config_entry_id": mock_config_entry.entry_id, "mac": MAC},
        blocking=True,
    )

    getattr(mock_omada_site_client, method).assert_awaited_once_with(MAC)


@pytest.mark.parametrize(("service", "method"), SERVICE_METHODS)
async def test_service_client_action_uses_first_controller(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Test client actions fall back to the first loaded controller."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, service, {"mac": MAC}, blocking=True)

    getattr(mock_omada_site_client, method).assert_awaited_once_with(MAC)


@pytest.mark.parametrize("service", SERVICE_PARAMS)
async def test_service_client_action_invalid_entry(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test client actions reject an unknown controller."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(
        ServiceValidationError, match="Specified TP-Link Omada controller not found"
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": "invalid_entry_id", "mac": MAC},
            blocking=True,
        )


@pytest.mark.parametrize("service", SERVICE_PARAMS)
async def test_service_client_action_entry_not_loaded(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test client actions reject a controller that is not loaded."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unloaded_entry = MockConfigEntry(
        title="Unloaded Omada Controller",
        domain=DOMAIN,
        unique_id="67890",
    )
    unloaded_entry.add_to_hass(hass)

    with pytest.raises(
        ServiceValidationError,
        match="The TP-Link Omada integration is not currently available",
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": unloaded_entry.entry_id, "mac": MAC},
            blocking=True,
        )


@pytest.mark.parametrize(("service", "method", "action"), SERVICE_ACTIONS)
async def test_service_client_action_failure(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
    action: str,
) -> None:
    """Test client actions translate API errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    getattr(mock_omada_site_client, method).side_effect = OmadaClientException()
    with pytest.raises(
        HomeAssistantError, match=f"Failed to {action} client with MAC {MAC}"
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": mock_config_entry.entry_id, "mac": MAC},
            blocking=True,
        )

    getattr(mock_omada_site_client, method).assert_awaited_once_with(MAC)


@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param(SERVICE_BLOCK, "block_client", id="block"),
        pytest.param(SERVICE_UNBLOCK, "unblock_client", id="unblock"),
    ],
)
async def test_service_client_access_action_requires_admin(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    mock_omada_site_client: MagicMock,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Test block and unblock services require an admin user."""
    hass_read_only_user.mock_policy({"entities": {"all": {"control": True}}})
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": mock_config_entry.entry_id, "mac": MAC},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    getattr(mock_omada_site_client, method).assert_not_awaited()
