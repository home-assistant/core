"""KAT Bulgaria Client Wrapper."""

from kat_bulgaria.data_models import KatObligation
from kat_bulgaria.kat_api_client import KatApiClient

from homeassistant.core import HomeAssistant


class KatClient:
    """KAT Client Manager."""

    person_name: str
    person_egn: str
    person_license_number: str

    api: KatApiClient
    hass: HomeAssistant

    def __init__(
        self, hass: HomeAssistant, name: str, egn: str, license_number: str
    ) -> None:
        """Initialize client."""
        super().__init__()

        self.person_name = name
        self.person_egn = egn
        self.person_license_number = license_number

        self.api = KatApiClient()
        self.hass = hass

    async def validate_credentials(self) -> bool:
        """Validate EGN/License Number."""
        return await self.api.validate_credentials(
            self.person_egn, self.person_license_number
        )

    async def get_obligations(self) -> list[KatObligation]:
        """Get obligations."""
        return await self.api.get_obligations(
            self.person_egn, self.person_license_number
        )
