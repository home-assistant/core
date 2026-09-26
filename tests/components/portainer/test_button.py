"""Tests for the Portainer button platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
from pyportainer.models.stacks import Stack, StackType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.portainer.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    snapshot_platform,
)

BUTTON_DOMAIN = "button"
UPDATE_STACK_ENTITY_ID = "button.webstack_update_stack"


async def test_all_button_entities_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all Portainer button entities."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.BUTTON],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("action", "client_method"),
    [
        ("restart", "restart_container"),
    ],
)
async def test_buttons_containers(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    client_method: str,
) -> None:
    """Test pressing a Portainer container button triggers call."""
    await setup_integration(hass, mock_config_entry)

    entity_id = f"button.practical_morse_{action}_container"
    method_mock = getattr(mock_portainer_client, client_method)
    pre_calls = len(method_mock.mock_calls)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(method_mock.mock_calls) == pre_calls + 1


@pytest.mark.parametrize(
    ("exception", "client_method"),
    [
        (PortainerAuthenticationError("auth"), "restart_container"),
        (PortainerConnectionError("conn"), "restart_container"),
        (PortainerTimeoutError("timeout"), "restart_container"),
    ],
)
async def test_buttons_containers_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    client_method: str,
) -> None:
    """Test that Portainer buttons, but this time when they will do boom for sure."""
    await setup_integration(hass, mock_config_entry)

    action = client_method.split("_", maxsplit=1)[0]
    entity_id = f"button.practical_morse_{action}_container"

    method_mock = getattr(mock_portainer_client, client_method)
    method_mock.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("action", "client_method"),
    [
        ("prune", "images_prune"),
    ],
)
async def test_buttons_endpoint(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    client_method: str,
) -> None:
    """Test pressing a Portainer endpoint button triggers call."""
    await setup_integration(hass, mock_config_entry)

    entity_id = f"button.my_environment_{action}_unused_images"
    method_mock = getattr(mock_portainer_client, client_method)
    pre_calls = len(method_mock.mock_calls)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(method_mock.mock_calls) == pre_calls + 1


@pytest.mark.parametrize(
    ("exception", "client_method"),
    [
        (PortainerAuthenticationError("auth"), "images_prune"),
        (PortainerConnectionError("conn"), "images_prune"),
        (PortainerTimeoutError("timeout"), "images_prune"),
    ],
)
async def test_buttons_endpoints_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    client_method: str,
) -> None:
    """Test that Portainer buttons, but this time when they will do boom for sure."""
    await setup_integration(hass, mock_config_entry)

    method_mock = getattr(mock_portainer_client, client_method)
    method_mock.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.my_environment_prune_unused_images"},
            blocking=True,
        )


async def test_button_update_stack(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing the update stack button redeploys the stack."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: UPDATE_STACK_ENTITY_ID},
        blocking=True,
    )

    mock_portainer_client.update_stack.assert_called_once_with(
        1, 1, timeout=timedelta(minutes=10)
    )


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (PortainerAuthenticationError("auth"), "invalid_auth"),
        (PortainerConnectionError("conn"), "cannot_connect"),
        (PortainerTimeoutError("timeout"), "timeout_connect"),
    ],
)
async def test_button_update_stack_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test the update stack button raises a translated error when the update fails."""
    await setup_integration(hass, mock_config_entry)
    mock_portainer_client.update_stack.side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: UPDATE_STACK_ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key


async def test_button_update_stack_not_for_kubernetes(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Kubernetes stacks don't get an update button."""
    stacks = await async_load_json_array_fixture(hass, "stacks.json", DOMAIN)
    stacks[0]["Type"] = StackType.KUBERNETES
    mock_portainer_client.get_stacks.return_value = [
        Stack.from_dict(stack) for stack in stacks
    ]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(UPDATE_STACK_ENTITY_ID) is None
    assert hass.states.get("button.dashy_update_stack") is not None
