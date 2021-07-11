"""Test helpers for decora_wifi."""

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.iot_switch import IotSwitch
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount
from decora_wifi.models.residential_permission import ResidentialPermission

from homeassistant.components.decora_wifi.common import DecoraWifiPlatform
from homeassistant.core import HomeAssistant


class MockDecoraWifiPlatform(DecoraWifiPlatform):
    """Class to simulate decora_wifi platform sessions and related methods for unit testing."""

    def __init__(self, email: str, password: str) -> None:
        """Iniialize session holder."""
        self._email = email
        self._password = password

    def __del__(self):
        """Clean up the session on object deletion."""
        pass

    @staticmethod
    async def async_setup_decora_wifi(hass: HomeAssistant, email: str, password: str):
        """Set up a mock decora wifi session."""

        def setupplatform():
            return MockDecoraWifiPlatform(email, password)

        return await hass.async_add_executor_job(setupplatform)


class FakeDecoraWiFiSession(DecoraWiFiSession):
    """Class to simulate the decora_wifi api class for testing common code."""

    def __init__(self):
        """Initialize the stub session."""
        super().__init__()
        self._email = None
        self._password = None
        self.user = None
        self._session = None

    def login(self, email, password):
        """Emulate login to LCS."""
        if "incoreect" in password:
            self._email = None
            self._password = None
            self.user = None
            return None

        self._email = email
        self._password = password
        self.user = FakeDecoraWiFiPerson(self)
        return True

    def call_api(self, api=None, payload=None, method="get"):
        """Try to prevent accidental calling of the real api."""
        return None


class FakeDecoraWiFiPerson(Person):
    """Class to simulate the decora_wifi api models/Person class."""

    def __init__(self, session, model_id=None):
        """Initialize the fake Person class."""
        super().__init__(session, model_id=model_id)
        self._perms = [
            FakeDecoraWiFiResidentialPermission(session, "fake_raID"),
            FakeDecoraWiFiResidentialPermission(session, "fake_rID"),
        ]

    def get_residential_permissions(self, attribs=None):
        """Return a list of permissions for testing the getdevices code."""
        return self._perms


class FakeDecoraWiFiResidentialPermission(ResidentialPermission):
    """Class to simulate the decora_wifi api permissions."""

    def __init__(self, session, model_id=None):
        """Initialize the fake permission class."""
        super().__init__(session, model_id=model_id)
        self._account = model_id == "fake_raID"

    @property
    def residentialAccountId(self):
        """Override the residentialAccounId property."""
        if self._account:
            return "fake_raID"
        return None

    @property
    def residenceId(self):
        """Override the residenceId property."""
        if not self._account:
            return "fake_rID"
        return None


class FakeDecoraWiFiResidence(Residence):
    """Class to simulate the decora_wifi api Residence class."""

    __idcounter = 0

    def __init__(self, session, model_id=None):
        """Initialize the fake Residence class."""
        super().__init__(session, model_id=model_id)
        self._session = session
        self._model_id = model_id
        self._number = self.nextID()
        self._iot_switches = [
            FakeDecoraWiFiIotSwitch(session),
            FakeDecoraWiFiIotSwitch(session),
        ]

    def get_iot_switches(self):
        """Return a list of simulated switch objects."""
        return self._iot_switches

    @classmethod
    def nextID(cls):
        """Generate Sequential Ids so the data fed to getdevices is unique."""
        cls.__idcounter += 1
        return cls.__idcounter


class FakeDecoraWiFiResidentialAccount(ResidentialAccount):
    """Class to simulate the decora_wifi api ResidentialAccount class."""

    def __init__(self, session, model_id=None):
        """Initialize the fake ResidentialAccount class."""
        super().__init__(session, model_id=model_id)
        self._session = session
        self._model_id = model_id
        self._residences = [
            FakeDecoraWiFiResidence(session),
            FakeDecoraWiFiResidence(session),
        ]

    def get_residences(self, attribs=None):
        """Override the get_residences method."""
        return self._residences


class FakeDecoraWiFiIotSwitch(IotSwitch):
    """Class to simulate the decora_wifi IotSwitch class."""

    __idcounter = 0

    def __init__(self, session, model_id=None):
        """Initialize the fake IotSwitch class."""
        super().__init__(session, model_id=model_id)
        self._number = self.nextID()

    @property
    def mac(self):
        """Override the mac property."""
        digits1 = self._number // 256
        digits2 = self._number % 256
        return f"DE-AD-BE-EF-{digits1}-{digits2}"

    @property
    def model(self):
        """Override the model property."""
        return f"fake_iot_sw {self.model_id}"

    @classmethod
    def nextID(cls):
        """Generate Sequential Ids so the data fed to getdevices is unique."""
        cls.__idcounter += 1
        return cls.__idcounter
