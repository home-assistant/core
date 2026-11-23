"""Tests for the Portainer button platform."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, _Call, call, patch

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerImagePullError,
    PortainerNotFoundError,
    PortainerTimeoutError,
)
from pyportainer.models.docker_inspect import DockerInspect
from pyportainer.models.image_pull import DockerImagePullEvent
from pyportainer.models.stacks import Stack, StackType
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    load_json_value_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import ButtonService
from homeassistant.components.portainer.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

BUTTON_DOMAIN = "button"
UPDATE_STACK_ENTITY_ID = "button.webstack_update_stack"
PULL_IMAGE_ENTITY_ID = "button.practical_morse_pull_image"


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
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: entity_id},
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
            ButtonService.PRESS,
            {TargetKey.ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_buttons_invalid_auth_starts_reauth(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an invalid API key on press starts a reauth flow."""
    await setup_integration(hass, mock_config_entry)
    mock_portainer_client.restart_container.side_effect = PortainerAuthenticationError(
        "auth"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {TargetKey.ENTITY_ID: "button.practical_morse_restart_container"},
            blocking=True,
        )
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.parametrize(
    ("entity_id", "client_method", "expected_call"),
    [
        pytest.param(
            "button.my_environment_prune_unused_images",
            "images_prune",
            call(endpoint_id=1, dangling=False, until=timedelta(days=0)),
            id="images",
        ),
        pytest.param(
            "button.my_environment_prune_unused_volumes",
            "prune_volumes",
            call(1),
            id="volumes",
        ),
        pytest.param(
            "button.my_environment_prune_build_cache",
            "prune_build_cache",
            call(1, all_cache=True),
            id="build_cache",
        ),
        pytest.param(
            "button.my_environment_prune_unused_networks",
            "prune_networks",
            call(1),
            id="networks",
        ),
    ],
)
async def test_buttons_endpoint(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    client_method: str,
    expected_call: _Call,
) -> None:
    """Test pressing a Portainer endpoint button calls the library."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    assert getattr(mock_portainer_client, client_method).mock_calls == [expected_call]


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
            ButtonService.PRESS,
            {TargetKey.ENTITY_ID: "button.my_environment_prune_unused_images"},
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
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: UPDATE_STACK_ENTITY_ID},
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
            ButtonService.PRESS,
            {TargetKey.ENTITY_ID: UPDATE_STACK_ENTITY_ID},
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


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(
            PortainerImagePullError("unauthorized: authentication required"),
            "image_pull_failed",
            id="pull_error",
        ),
        pytest.param(
            PortainerNotFoundError("pull access denied"),
            "image_pull_failed",
            id="not_found",
        ),
        pytest.param(PortainerAuthenticationError("auth"), "invalid_auth", id="auth"),
    ],
)
async def test_button_pull_image_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test the pull image button raises a translated error when the pull fails."""
    await setup_integration(hass, mock_config_entry)
    mock_portainer_client.image_pull.side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {TargetKey.ENTITY_ID: PULL_IMAGE_ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key


async def test_button_pull_image_timeout(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a pull that takes too long raises a timeout error."""

    async def _image_pull(
        endpoint_id: int, image: str
    ) -> AsyncGenerator[DockerImagePullEvent]:
        await asyncio.Event().wait()
        yield DockerImagePullEvent()

    mock_portainer_client.image_pull.side_effect = _image_pull
    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.portainer.button.PULL_IMAGE_TIMEOUT",
            timedelta(0),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {TargetKey.ENTITY_ID: PULL_IMAGE_ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == "image_pull_timeout"


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        pytest.param("nginx", "nginx:latest", id="untagged"),
        pytest.param(
            "registry:5000/foo", "registry:5000/foo:latest", id="registry_port"
        ),
        pytest.param("nginx:1.27", "nginx:1.27", id="tagged"),
        pytest.param(
            "nginx@sha256:0123456789abcdef",
            "nginx@sha256:0123456789abcdef",
            id="digest",
        ),
    ],
)
async def test_button_pull_image_reference(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    image: str,
    expected: str,
) -> None:
    """Test the pull image button pulls an explicit tag instead of every tag."""
    inspect = cast(
        dict[str, Any], load_json_value_fixture("container_inspect.json", DOMAIN)
    )
    inspect["Config"]["Image"] = image
    mock_portainer_client.inspect_container.return_value = DockerInspect.from_dict(
        inspect
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: PULL_IMAGE_ENTITY_ID},
        blocking=True,
    )

    mock_portainer_client.image_pull.assert_called_once_with(1, expected)
    mock_portainer_client.container_recreate.assert_not_called()


async def test_button_pull_image_unavailable_without_config_image(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the pull image button is unavailable when the container has no image."""
    inspect = cast(
        dict[str, Any], load_json_value_fixture("container_inspect.json", DOMAIN)
    )
    del inspect["Config"]
    mock_portainer_client.inspect_container.return_value = DockerInspect.from_dict(
        inspect
    )

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(PULL_IMAGE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
