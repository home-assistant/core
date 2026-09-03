"""Notify platform for the Famn integration."""

from typing import TYPE_CHECKING, override

from famn_sdk import ApiError, NotifySpaceRequest, SpaceMember

from homeassistant.components.notify import NotifyEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import FamnConfigEntry
from .entity import famn_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FamnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notify platform from a config entry."""
    async_add_entities([FamnNotifyEntity(entry)])

    scores = entry.runtime_data.scores
    known_members: set[str] = set()

    @callback
    def add_member_entities() -> None:
        """Add notify entities for members that appeared in the space.

        Local members without an account have no phone to push to and get
        no entity.
        """
        members = {
            member.account_id: member
            for member in scores.data.members
            if member.account_id is not None
        }
        if new_members := set(members) - known_members:
            async_add_entities(
                FamnMemberNotifyEntity(entry, members[account_id])
                for account_id in new_members
            )
            known_members.update(new_members)

    entry.async_on_unload(scores.async_add_listener(add_member_entities))
    add_member_entities()


class FamnNotifyEntity(NotifyEntity):
    """Send a notification to every member of the paired Famn space.

    The message is pushed to each family member's phone and lands in the
    Famn app's notification inbox, attributed to this Home Assistant
    pairing. Famn rate-limits the device, so a runaway automation cannot
    spam the family.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "family"

    def __init__(self, entry: FamnConfigEntry) -> None:
        """Initialize the notify entity."""
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_notify"
        self._attr_device_info = famn_device_info(entry)

    async def _async_notify(
        self, message: str, title: str | None, account_id: str | None
    ) -> None:
        """Send the message via Famn, to one member or the whole space."""
        scores = self._entry.runtime_data.scores

        if TYPE_CHECKING:
            assert self._entry.unique_id is not None

        try:
            await scores.auth.async_ensure_token_valid()
            await scores.space_api.notify_space_endpoint(
                self._entry.unique_id,
                body=NotifySpaceRequest(
                    title=title or "Home Assistant",
                    message=message,
                    account_id=account_id,
                ),
            )
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="notify_failed",
            ) from err

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send the message to the family's phones."""
        await self._async_notify(message, title, None)


class FamnMemberNotifyEntity(FamnNotifyEntity):
    """Send a notification to one member of the paired Famn space."""

    _attr_translation_key = None

    def __init__(self, entry: FamnConfigEntry, member: SpaceMember) -> None:
        """Initialize the member notify entity."""
        super().__init__(entry)
        if TYPE_CHECKING:
            assert member.account_id is not None
        self._account_id = member.account_id
        self._attr_unique_id = f"{entry.unique_id}_notify_{member.account_id}"
        self._attr_name = member.display_name or member.account_id

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send the message to this member's phone."""
        await self._async_notify(message, title, self._account_id)
