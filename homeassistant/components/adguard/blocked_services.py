"""AdGuardHome blocked services"""
from adguardhome import AdGuardHome


class BlockedServices:
    """Class for keeping track of the blocked services"""

    def __init__(self, adguard: AdGuardHome, blocked_services: list[str]) -> None:
        """Initialize AdGuard Block Services class"""
        self._blocked_services = blocked_services
        self._adguard = adguard

    async def is_blocked(self, service_id: str, *args) -> bool:
        """Check if a specific service is blocked"""
        return service_id in self._blocked_services

    async def block(self, service_id: str, *args) -> None:
        """Block a specific service"""
        self._blocked_services.append(service_id)
        await self._adguard.blocked_services.set_blocked_services(
            self._blocked_services
        )

    async def unblock(self, service_id: str, *args) -> None:
        """Unblock a specific service"""
        self._blocked_services.remove(service_id)
        await self._adguard.blocked_services.set_blocked_services(
            self._blocked_services
        )
