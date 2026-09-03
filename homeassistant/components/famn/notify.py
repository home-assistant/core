"""Notify platform for the Famn integration."""

from typing import TYPE_CHECKING, override

from famn_sdk import ApiError, NotifySpaceRequest, SpaceMember

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FamnConfigEntry, FamnScoresCoordinator
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
                FamnMemberNotifyEntity(scores, members[account_id])
                for account_id in new_members
            )
            known_members.update(new_members)

    entry.async_on_unload(scores.async_add_listener(add_member_entities))
    add_member_entities()


async def _async_notify(
    entry: FamnConfigEntry, message: str, title: str | None, account_id: str | None
) -> None:
    """Send a message via Famn, to one member or the whole space.

    The message reaches the recipients' phones and lands in the Famn app's
    notification inbox, attributed to this Home Assistant pairing.
    """
    scores = entry.runtime_data.scores

    if TYPE_CHECKING:
        assert entry.unique_id is not None

    try:
        await scores.auth.async_ensure_token_valid()
        await scores.space_api.notify_space_endpoint(
            entry.unique_id,
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


class FamnNotifyEntity(NotifyEntity):
    """Send a notification to every member of the paired Famn space."""

    _attr_has_entity_name = True
    _attr_translation_key = "family"
    # Famn shows the title as the heading of the notification in its inbox.
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: FamnConfigEntry) -> None:
        """Initialize the family notify entity."""
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_family"
        self._attr_device_info = famn_device_info(entry)

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send the message to the family's phones."""
        await _async_notify(self._entry, message, title, None)


class FamnMemberNotifyEntity(CoordinatorEntity[FamnScoresCoordinator], NotifyEntity):
    """Send a notification to one member of the paired Famn space."""

    _attr_has_entity_name = True
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, coordinator: FamnScoresCoordinator, member: SpaceMember) -> None:
        """Initialize the member notify entity."""
        super().__init__(coordinator)

        entry = coordinator.config_entry
        if TYPE_CHECKING:
            assert member.account_id is not None

        self._entry = entry
        self._account_id = member.account_id
        self._attr_unique_id = f"{entry.unique_id}_{member.account_id}"
        # Named after the member, so no translation key applies here.
        self._attr_name = member.display_name or member.account_id
        self._attr_device_info = famn_device_info(entry)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Keep the entity name in step with the member's display name."""
        if (member := self._member()) is not None:
            self._attr_name = member.display_name or self._account_id
        super()._handle_coordinator_update()

    def _member(self) -> SpaceMember | None:
        """Return the member's current roster entry, if they are still there."""
        return next(
            (
                member
                for member in self.coordinator.data.members
                if member.account_id == self._account_id
            ),
            None,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the member is still part of the Famn space.

        A member who left has no phone to reach any more, so the entity goes
        unavailable rather than pushing to a stale account.
        """
        return super().available and self._member() is not None

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send the message to this member's phone."""
        await _async_notify(self._entry, message, title, self._account_id)
