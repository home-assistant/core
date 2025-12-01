"""Party coordinator for the Habitica integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from habiticalib import GroupData, UserData

from .base import HabiticaBaseCoordinator


@dataclass
class HabiticaPartyData:
    """Habitica party data."""

    party: GroupData
    members: dict[UUID, UserData]


class HabiticaPartyCoordinator(HabiticaBaseCoordinator[HabiticaPartyData]):  # pylint: disable=hass-enforce-class-module
    """Habitica Party Coordinator."""

    _update_interval = timedelta(minutes=15)

    async def _update_data(self) -> HabiticaPartyData:
        """Fetch the latest party data."""

        return HabiticaPartyData(
            party=(await self.habitica.get_group()).data,
            members={
                member.id: member
                for member in (
                    await self.habitica.get_group_members(public_fields=True)
                ).data
                if member.id
            },
        )
