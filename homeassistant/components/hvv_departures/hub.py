"""Hub."""

from pygti.gti import GTI, Auth

from homeassistant.config_entries import ConfigEntry

type HVVConfigEntry = ConfigEntry[GTIHub]


class GTIHub:
    """GTI Hub."""

    def __init__(self, host, username, password, session):
        """Initialize."""
        self.host = host
        self.username = username
        self.password = password

        self.gti = GTI(Auth(session, self.username, self.password, self.host))

    async def authenticate(self):
        """Test if we can authenticate with the host."""

        return await self.gti.init()
