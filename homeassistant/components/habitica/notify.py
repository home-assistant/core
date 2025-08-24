"""Notify platform for the Habitica integration."""

from __future__ import annotations

from abc import abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from aiohttp import ClientError
from habiticalib import (
    GroupData,
    HabiticaException,
    NotAuthorizedError,
    NotFoundError,
    TooManyRequestsError,
    UserData,
)

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    NotifyEntity,
    NotifyEntityDescription,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HABITICA_KEY
from .const import DOMAIN
from .coordinator import HabiticaConfigEntry, HabiticaDataUpdateCoordinator
from .entity import HabiticaBase

PARALLEL_UPDATES = 10


class HabiticaNotify(StrEnum):
    """Habitica Notifier."""

    PARTY_CHAT = "party_chat"
    PRIVATE_MESSAGE = "private_message"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notify entity platform."""
    members_added: set[UUID] = set()
    entity_registry = er.async_get(hass)

    coordinator = config_entry.runtime_data

    if party := coordinator.data.user.party.id:
        party_coordinator = hass.data[HABITICA_KEY][party]
        async_add_entities(
            [HabiticaPartyChatNotifyEntity(coordinator, party_coordinator.data.party)]
        )

        @callback
        def add_entities() -> None:
            nonlocal members_added

            new_members = set(party_coordinator.data.members.keys()) - members_added
            if TYPE_CHECKING:
                assert coordinator.data.user.id
            new_members.discard(coordinator.data.user.id)
            if new_members:
                async_add_entities(
                    [
                        HabiticaPrivateMessageNotifyEntity(
                            coordinator, party_coordinator.data.members[member]
                        )
                        for member in new_members
                    ]
                )
                members_added |= new_members

            delete_members = members_added - set(party_coordinator.data.members.keys())
            for member in delete_members:
                if entity_id := entity_registry.async_get_entity_id(
                    NOTIFY_DOMAIN,
                    DOMAIN,
                    f"{coordinator.config_entry.unique_id}_{member!s}_{HabiticaNotify.PRIVATE_MESSAGE}",
                ):
                    entity_registry.async_remove(entity_id)

                members_added.discard(member)

        party_coordinator.async_add_listener(add_entities)
        add_entities()


class HabiticaBaseNotifyEntity(HabiticaBase, NotifyEntity):
    """Habitica base notify entity."""

    entity_description: NotifyEntityDescription

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
    ) -> None:
        """Initialize a Habitica entity."""
        super().__init__(coordinator, self.entity_description)

    @abstractmethod
    async def _send_message(self, message: str) -> None:
        """Send a Habitica message."""

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        if TYPE_CHECKING:
            assert self.entity_description.translation_placeholders
        try:
            await self._send_message(message)
        except NotAuthorizedError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_forbidden",
                translation_placeholders={
                    **self.entity_description.translation_placeholders,
                    "reason": e.error.message,
                },
            ) from e
        except NotFoundError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_not_found",
                translation_placeholders={
                    **self.entity_description.translation_placeholders,
                    "reason": e.error.message,
                },
            ) from e
        except TooManyRequestsError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="setup_rate_limit_exception",
                translation_placeholders={"retry_after": str(e.retry_after)},
            ) from e
        except HabiticaException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": e.error.message},
            ) from e
        except ClientError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": str(e)},
            ) from e


class HabiticaPartyChatNotifyEntity(HabiticaBaseNotifyEntity):
    """Representation of a Habitica party chat notify entity."""

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        party: GroupData,
    ) -> None:
        """Initialize a Habitica entity."""
        self.entity_description = NotifyEntityDescription(
            key=HabiticaNotify.PARTY_CHAT,
            translation_key=HabiticaNotify.PARTY_CHAT,
            translation_placeholders={CONF_NAME: party.name},
        )
        self.party = party
        super().__init__(coordinator)

    async def _send_message(self, message: str) -> None:
        """Send a Habitica party chat message."""

        await self.coordinator.habitica.send_group_message(
            message=message,
            group_id=self.party.id,
        )


class HabiticaPrivateMessageNotifyEntity(HabiticaBaseNotifyEntity):
    """Representation of a Habitica private message notify entity."""

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        member: UserData,
    ) -> None:
        """Initialize a Habitica entity."""

        self.entity_description = NotifyEntityDescription(
            key=f"{member.id!s}_{HabiticaNotify.PRIVATE_MESSAGE}",
            translation_key=HabiticaNotify.PRIVATE_MESSAGE,
            translation_placeholders={CONF_NAME: member.profile.name or ""},
        )
        self.member = member
        super().__init__(coordinator)

    async def _send_message(self, message: str) -> None:
        """Send a Habitica private message."""
        if TYPE_CHECKING:
            assert self.member.id
        await self.coordinator.habitica.send_private_message(
            message=message,
            to_user_id=self.member.id,
        )
