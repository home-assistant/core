"""Permission checks for AI tasks."""

from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized, UnknownUser


async def async_check_permissions(
    hass: HomeAssistant,
    entity_id: str | None,
    attachments: list[dict] | None,
    context: Context | None,
) -> None:
    """Check access to explicitly selected entities and entity attachments."""
    if context is None or context.user_id is None:
        return

    if (user := await hass.auth.async_get_user(context.user_id)) is None:
        raise UnknownUser(context=context)

    if entity_id is not None and not user.permissions.check_entity(
        entity_id, POLICY_CONTROL
    ):
        raise Unauthorized(
            context=context, entity_id=entity_id, permission=POLICY_CONTROL
        )

    for attachment in attachments or []:
        media_content_id = attachment["media_content_id"]
        for domain in ("camera", "image"):
            prefix = f"media-source://{domain}/"
            if not media_content_id.startswith(prefix):
                continue
            attachment_entity_id = media_content_id.removeprefix(prefix)
            if not user.permissions.check_entity(attachment_entity_id, POLICY_READ):
                raise Unauthorized(
                    context=context,
                    entity_id=attachment_entity_id,
                    permission=POLICY_READ,
                )
            break
