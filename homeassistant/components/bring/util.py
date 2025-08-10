"""Utility functions for Bring."""

from __future__ import annotations

from bring_api import BringUserSettingsResponse

from .coordinator import BringData


def list_language(
    list_uuid: str,
    user_settings: BringUserSettingsResponse,
) -> str | None:
    """Get the lists language setting."""
    try:
        list_settings = next(
            filter(lambda x: x.listUuid == list_uuid, user_settings.userlistsettings)
        )

        return (
            next(
                filter(
                    lambda x: x.key == "listArticleLanguage", list_settings.usersettings
                )
            )
        ).value

    except StopIteration:
        return None


def sum_attributes(bring_list: BringData, attribute: str) -> int:
    """Count items with given attribute set."""
    return sum(
        getattr(item.attributes[0].content, attribute)
        for item in bring_list.content.items.purchase
        if item.attributes
    )
