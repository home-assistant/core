"""Test helpers for decora_wifi."""

from __future__ import annotations

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.iot_switch import IotSwitch
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount
from decora_wifi.models.residential_permission import ResidentialPermission

# Test Inputs
SWITCH_NAME = "fake_switch"
MANUFACTURER = "Leviton Manufacturing Co., Inc."
VERSION = "1.5.72; CP 1.19"
CAN_SET_LEVEL = [
    "D26HD",
    "D23LP",
    "DW4SF",
    "DWVAA",
]


class FakeDecoraWiFiAccount:
    """Class to simulate an account info in the API."""

    def __init__(
        self,
        email: str,
        password: str,
        bare_res_perm: bool = False,
        switch_models=None,
    ) -> None:
        """Initialize the stub account."""
        self.email = email
        self.password = password
        self.bare_res_perm = bare_res_perm
        if switch_models:
            self.switch_models = switch_models
        else:
            self.switch_models: list(str) = []


class FakeDecoraWiFiSession(DecoraWiFiSession):
    """Class to simulate the decora_wifi api class for testing common code."""

    _fake_api_accounts = {}

    def __init__(self):
        """Initialize the stub session."""
        self.data = {}
        self.email = None
        self.password = None
        self.user = None
        self.acct = None
        self.comms_good = True

    def login(self, email, password):
        """Emulate login to LCS."""
        self.acct = self.get_account(email)
        if self.acct:
            # Process simulated login with custom account info
            if not password == self.acct.password:
                return None
            self.email = email
            self.password = password
            self.user = FakeDecoraWiFiPerson(self)
            return self.user

        # Process simulated login with default account info
        self.email = email
        self.password = password
        self.acct = FakeDecoraWiFiAccount(email, password, False, ["default"])
        self.add_account(self.acct)
        self.user = FakeDecoraWiFiPerson(self)
        return self.user

    def call_api(self, api=None, payload=None, method="get"):
        """Try to prevent accidental calling of the real api."""
        return None

    @classmethod
    def add_account(cls, account: FakeDecoraWiFiAccount):
        """Add a user account to the simulated API."""
        cls._fake_api_accounts.update({account.email: account})

    @classmethod
    def clear_accounts(cls):
        """Clear accounts from the simulated API."""
        cls._fake_api_accounts = {}

    @classmethod
    def get_account(cls, email: str) -> FakeDecoraWiFiAccount:
        """Get a user account from the simulated API."""
        if email in cls._fake_api_accounts:
            return cls._fake_api_accounts[email]
        return None


class FakeDecoraWiFiPerson(Person):
    """Class to simulate the decora_wifi api models/Person class."""

    def __init__(self, session, model_id=None):
        """Initialize the fake Person class."""
        self.data = {}
        if session.acct.bare_res_perm:
            self._perms = [FakeDecoraWiFiResidentialPermission(session, "fake_rID")]
        else:
            self._perms = [FakeDecoraWiFiResidentialPermission(session, "fake_raID")]
        self._model_id = model_id
        self._session = session

    def get_residential_permissions(self, attribs=None):
        """Return a list of permissions for testing the getdevices code."""
        return self._perms


class FakeDecoraWiFiResidentialPermission(ResidentialPermission):
    """Class to simulate the decora_wifi api permissions."""

    def __init__(self, session, model_id=None):
        """Initialize the fake permission class."""
        self.data = {}
        self._session = session
        self._model_id = model_id
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

    __id_counter = 0

    def __init__(self, session, model_id=None):
        """Initialize the fake Residence class."""
        self.data = {}
        self._session = session
        self._model_id = model_id
        self._number = self.next_id()
        self._iot_switches = []
        for model in session.acct.switch_models:
            self._iot_switches.append(FakeDecoraWiFiIotSwitch(session, model))

    def get_iot_switches(self, attribs=None):
        """Return a list of simulated switch objects."""
        return self._iot_switches

    @classmethod
    def next_id(cls):
        """Generate Sequential Ids so the data fed to getdevices is unique."""
        cls.__id_counter += 1
        return cls.__id_counter

    @classmethod
    def reset_counter(cls):
        """Reset the Id counter."""
        cls.__id_counter = 0


class FakeDecoraWiFiResidentialAccount(ResidentialAccount):
    """Class to simulate the decora_wifi api ResidentialAccount class."""

    def __init__(self, session, model_id=None):
        """Initialize the fake ResidentialAccount class."""
        self.data = {}
        self._session = session
        self._model_id = model_id
        self._residences = [
            FakeDecoraWiFiResidence(session),
        ]

    def get_residences(self, attribs=None):
        """Override the get_residences method."""
        return self._residences


class FakeDecoraWiFiIotSwitch(IotSwitch):
    """Class to simulate the decora_wifi IotSwitch class."""

    __id_counter = 0

    def __init__(self, session, model_id=None):
        """Initialize the fake IotSwitch class."""
        super().__init__(session, model_id)
        self._session = session
        if not model_id:
            self._id = "D26HD"
        self.canSetLevel = model_id in CAN_SET_LEVEL
        self._number = self.next_id()
        self.data.update(
            {
                "brightness": 100,
                "mac": f"DE-AD-BE-EF-00-{self._number:02x}",
                "manufacturer": MANUFACTURER,
                "name": f"{SWITCH_NAME}_{self._number}",
                "model": self._id,
                "power": "ON",
                "version": VERSION,
            }
        )

    def refresh(self):
        """Override of the API's refresh for testing."""
        pass

    def update_attributes(self, attribs=None):
        """Override of the API's update_attributes for testing."""
        if self._session.comms_good:
            self.data.update(attribs)
        else:
            raise ValueError("myLeviton API call failed.")

    @classmethod
    def next_id(cls):
        """Generate Sequential Ids so the data fed to getdevices is unique."""
        cls.__id_counter += 1
        return cls.__id_counter

    @classmethod
    def reset_counter(cls):
        """Reset the Id counter."""
        cls.__id_counter = 0
