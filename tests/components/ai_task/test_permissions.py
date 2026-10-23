"""Test AI task permissions."""

import pytest

from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components.ai_task.permissions import async_check_permissions
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized, UnknownUser

from .conftest import TEST_ENTITY_ID

from tests.common import MockUser


@pytest.mark.parametrize("context", [None, Context()])
async def test_system_context(hass: HomeAssistant, context: Context | None) -> None:
    """System tasks can use entities without a user permission check."""
    await async_check_permissions(
        hass,
        TEST_ENTITY_ID,
        [{"media_content_id": "media-source://camera/camera.test"}],
        context,
    )


async def test_unknown_user(hass: HomeAssistant) -> None:
    """An unknown user cannot use even the default task entity."""
    context = Context(user_id="unknown")
    with pytest.raises(UnknownUser) as err:
        await async_check_permissions(hass, None, None, context)
    assert err.value.context is context


async def test_explicit_entity_denied(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Explicitly selected task entities require control permission."""
    context = Context(user_id=hass_read_only_user.id)
    with pytest.raises(Unauthorized) as err:
        await async_check_permissions(hass, TEST_ENTITY_ID, None, context)
    assert err.value.context is context
    assert err.value.entity_id == TEST_ENTITY_ID
    assert err.value.permission == POLICY_CONTROL


async def test_explicit_entity_allowed(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Users with control permission can select a task entity."""
    await async_check_permissions(
        hass, TEST_ENTITY_ID, None, Context(user_id=hass_admin_user.id)
    )


async def test_default_entity(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Using the default task entity does not require control permission."""
    await async_check_permissions(
        hass, None, None, Context(user_id=hass_read_only_user.id)
    )


@pytest.mark.parametrize("domain", ["camera", "image"])
@pytest.mark.parametrize("entity_id", [None, TEST_ENTITY_ID])
async def test_attachment_denied(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    domain: str,
    entity_id: str | None,
) -> None:
    """Entity attachments need read permission even with a default task entity."""
    hass_admin_user.mock_policy(
        {"entities": {"entity_ids": {TEST_ENTITY_ID: {"control": True}}}}
    )
    context = Context(user_id=hass_admin_user.id)
    attachment_entity_id = f"{domain}.test"
    with pytest.raises(Unauthorized) as err:
        await async_check_permissions(
            hass,
            entity_id,
            [{"media_content_id": f"media-source://{domain}/{attachment_entity_id}"}],
            context,
        )
    assert err.value.context is context
    assert err.value.entity_id == attachment_entity_id
    assert err.value.permission == POLICY_READ


@pytest.mark.parametrize("domain", ["camera", "image"])
async def test_attachment_allowed(
    hass: HomeAssistant, hass_read_only_user: MockUser, domain: str
) -> None:
    """Read permission is sufficient for an entity attachment."""
    await async_check_permissions(
        hass,
        None,
        [{"media_content_id": f"media-source://{domain}/{domain}.test"}],
        Context(user_id=hass_read_only_user.id),
    )


async def test_local_media(hass: HomeAssistant, hass_read_only_user: MockUser) -> None:
    """Local media attachments do not have entity permissions."""
    hass_read_only_user.mock_policy({})
    await async_check_permissions(
        hass,
        None,
        [{"media_content_id": "media-source://media_source/local/test.png"}],
        Context(user_id=hass_read_only_user.id),
    )
