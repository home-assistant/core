"""Notify platform for PlayStation Network."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from psnawp_api.core.psnawp_exceptions import (
    PSNAWPClientError,
    PSNAWPForbiddenError,
    PSNAWPNotFoundError,
    PSNAWPServerError,
)
from psnawp_api.models.group.group import Group

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

from .const import DOMAIN
from .coordinator import (
    PlaystationNetworkConfigEntry,
    PlaystationNetworkFriendlistCoordinator,
    PlaystationNetworkGroupsUpdateCoordinator,
)
from .entity import PlaystationNetworkServiceEntity

PARALLEL_UPDATES = 20


class PlaystationNetworkNotify(StrEnum):
    """PlayStation Network sensors."""

    GROUP_MESSAGE = "group_message"
    DIRECT_MESSAGE = "direct_message"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PlaystationNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notify entity platform."""

    coordinator = config_entry.runtime_data.groups
    friends_list = config_entry.runtime_data.friends_list

    groups_added: set[str] = set()
    friends_added: set[str] = set()
    entity_registry = er.async_get(hass)

    @callback
    def add_entities() -> None:
        nonlocal groups_added

        new_groups = set(coordinator.data.keys()) - groups_added
        if new_groups:
            async_add_entities(
                PlaystationNetworkNotifyEntity(coordinator, group_id)
                for group_id in new_groups
            )
            groups_added |= new_groups

        deleted_groups = groups_added - set(coordinator.data.keys())
        for group_id in deleted_groups:
            if entity_id := entity_registry.async_get_entity_id(
                NOTIFY_DOMAIN,
                DOMAIN,
                f"{coordinator.config_entry.unique_id}_{group_id}",
            ):
                entity_registry.async_remove(entity_id)

    coordinator.async_add_listener(add_entities)
    add_entities()

    @callback
    def add_dm_entities() -> None:
        nonlocal friends_added

        new_friends = set(friends_list.psn.friends_list.keys()) - friends_added
        if new_friends:
            async_add_entities(
                [
                    PlaystationNetworkDirectMessageNotifyEntity(
                        friends_list, account_id
                    )
                    for account_id in new_friends
                ],
            )
            friends_added |= new_friends
        deleted_friends = friends_added - set(coordinator.psn.friends_list.keys())
        for account_id in deleted_friends:
            if entity_id := entity_registry.async_get_entity_id(
                NOTIFY_DOMAIN,
                DOMAIN,
                f"{coordinator.config_entry.unique_id}_{account_id}_{PlaystationNetworkNotify.DIRECT_MESSAGE}",
            ):
                entity_registry.async_remove(entity_id)

    friends_list.async_add_listener(add_dm_entities)
    add_dm_entities()


class PlaystationNetworkNotifyBaseEntity(PlaystationNetworkServiceEntity, NotifyEntity):
    """Base class of PlayStation Network notify entity."""

    group: Group | None = None

    def _send_message(self, message: str) -> None:
        """Send message."""
        if TYPE_CHECKING:
            assert self.group
        self.group.send_message(message)

    def send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""

        try:
            self._send_message(message)
        except PSNAWPNotFoundError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="group_invalid",
                translation_placeholders=dict(self.translation_placeholders),
            ) from e
        except PSNAWPForbiddenError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_forbidden",
                translation_placeholders=dict(self.translation_placeholders),
            ) from e
        except (PSNAWPServerError, PSNAWPClientError) as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_failed",
                translation_placeholders=dict(self.translation_placeholders),
            ) from e


class PlaystationNetworkNotifyEntity(PlaystationNetworkNotifyBaseEntity):
    """Representation of a PlayStation Network notify entity."""

    coordinator: PlaystationNetworkGroupsUpdateCoordinator

    def __init__(
        self,
        coordinator: PlaystationNetworkGroupsUpdateCoordinator,
        group_id: str,
    ) -> None:
        """Initialize a notification entity."""
        self.group = coordinator.psn.psn.group(group_id=group_id)
        group_details = coordinator.data[group_id]
        self.entity_description = NotifyEntityDescription(
            key=group_id,
            translation_key=PlaystationNetworkNotify.GROUP_MESSAGE,
            translation_placeholders={
                CONF_NAME: group_details["groupName"]["value"]
                or ", ".join(
                    member["onlineId"]
                    for member in group_details["members"]
                    if member["accountId"] != coordinator.psn.user.account_id
                )
            },
        )

        super().__init__(coordinator, self.entity_description)


class PlaystationNetworkDirectMessageNotifyEntity(PlaystationNetworkNotifyBaseEntity):
    """Representation of a PlayStation Network notify entity for sending direct messages."""

    coordinator: PlaystationNetworkFriendlistCoordinator

    def __init__(
        self,
        coordinator: PlaystationNetworkFriendlistCoordinator,
        account_id: str,
    ) -> None:
        """Initialize a notification entity."""
        self.account_id = account_id
        self.entity_description = NotifyEntityDescription(
            key=f"{account_id}_{PlaystationNetworkNotify.DIRECT_MESSAGE}",
            translation_key=PlaystationNetworkNotify.DIRECT_MESSAGE,
            translation_placeholders={
                CONF_NAME: coordinator.psn.friends_list[account_id].online_id
            },
            entity_registry_enabled_default=False,
        )

        super().__init__(coordinator, self.entity_description)

    def _send_message(self, message: str) -> None:
        if not self.group:
            self.group = self.coordinator.psn.psn.group(
                users_list=[self.coordinator.psn.friends_list[self.account_id]]
            )
        super()._send_message(message)
