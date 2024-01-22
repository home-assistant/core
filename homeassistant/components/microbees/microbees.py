"""microBees class."""
import logging

from microBeesPy.microbees import MicroBees

_LOGGER = logging.getLogger(__name__)


class MicroBeesConnector:
    """microBees class."""

    def __init__(
        self,
        client_id=None,
        client_secret=None,
        session=None,
        token=None,
    ) -> None:
        """Initialize."""
        self.microBees = MicroBees(client_id, client_secret, session, token)

    async def login(self, email, password):
        """Login to microBees."""
        access_token = await self.microBees.login(email, password)
        return access_token

    async def getBees(self):
        """Get Bees from microBees."""
        myBees = await self.microBees.getBees()
        return myBees

    async def sendCommand(self, actuatorID, relayValue):
        """Send command to microBees."""
        myBees = await self.microBees.sendCommand(actuatorID, relayValue)
        return myBees

    async def getMyBeesByIds(self, beeIDs):
        """Get Bees from microBees by IDs."""
        myBee = await self.microBees.getMyBeesByIds(beeIDs)
        return myBee

    async def getActuatorById(self, actuatorID):
        """Get Actuator from microBees by ID."""
        myBee = await self.microBees.getActuatorById(actuatorID)
        return myBee

    async def getMyProfile(self):
        """Get My Profile from microBees."""
        myBee = await self.microBees.getMyProfile()
        return myBee
