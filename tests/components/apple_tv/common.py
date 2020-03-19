"""Test code shared between test files."""

from functools import partial

from pyatv import conf, interface
from pyatv.const import Protocol

from homeassistant.data_entry_flow import AbortFlow


class MockPairingHandler(interface.PairingHandler):
    """Mock for PairingHandler in pyatv."""

    def __init__(self, *args):
        """Initialize a new MockPairingHandler."""
        super().__init__(*args)
        self.always_fail = False

    def pin(self, pin):
        """Pin code used for pairing."""
        self.pin_code = pin
        self.paired = False

    @property
    def device_provides_pin(self):
        """Return True if remote device presents PIN code, else False."""
        return self.service.protocol in [Protocol.MRP, Protocol.AirPlay]

    @property
    def has_paired(self):
        """If a successful pairing has been performed.

        The value will be reset when stop() is called.
        """
        return not self.always_fail and self.paired

    async def begin(self):
        """Start pairing process."""

    async def finish(self):
        """Stop pairing process."""
        self.paired = True
        self.service.credentials = self.service.protocol.name.lower() + "_creds"


class FlowInteraction:
    """Simulate user interaction in data entry flow.

    The general way of using this wrapper looks like this:

    (await FlowInteraction(flow).step_<STEP NAME>(<STEP INPUT>))
        .gives_<TYPE>(<EXPECTED OUTPUT>)

    Supported value for <TYPE> is form, abort or create_entry.

    Simulating that a user inputs username and password into the login
    step, yielding a config entry might look like this:

    (await FlowInteraction(flow).step_login(
          username="bob", password="alice")).gives_create_entry({
              "username": "bob",
              "password": "alice",
          })

    Another example where a user inputs a bad IP-address into the host field
    of the address step yields an abort:

    (await FlowInteraction(flow).step_address(
        host="12345").gives_abort("bad_host")
    """

    def __init__(self, flow):
        """Initialize a new FlowInteraction."""
        self.flow = flow
        self.name = None
        self.result = None
        self.exception = None

    def __getattr__(self, attr):
        """Return correct action method dynamically based on name."""
        prefix, name = attr.split("_", 1)
        if prefix == "step":
            self.name = name
            return self._step
        if prefix == "init":
            self.name = name
            return self._init
        if prefix == "gives":
            if name == "abort":
                return self._abort
            if name == "create_entry":
                return self._create_entry

            gives_type, gives_name = name.split("_", 1)
            return partial(getattr(self, "_" + gives_type), gives_name)

    async def _init(self, has_input=True, **user_input):
        args = {**user_input} if has_input else None
        self.result = await self.flow.hass.config_entries.flow.async_init(
            "apple_tv", data=args, context={"source": self.name}
        )
        return self

    async def _step(self, has_input=True, **user_input):
        args = {**user_input} if has_input else None
        try:
            self.result = await getattr(self.flow, "async_step_" + self.name)(args)
        except AbortFlow as ex:
            self.exception = ex
        return self

    def _form(self, step_id, **kwargs):
        assert self.result["type"] == "form"
        assert self.result["step_id"] == step_id
        for key, value in kwargs.items():
            assert self.result[key] == value

    def _create_entry(self, entry):
        assert self.result["type"] == "create_entry"
        assert self.result["data"] == entry

    def _abort(self, reason):
        if self.result:
            assert self.result["type"] == "abort"
            assert self.result["reason"] == reason
        else:
            assert self.exception.reason, reason


def create_conf(name, address, *services):
    """Create an Apple TV configuration."""
    atv = conf.AppleTV(name, address)
    for service in services:
        atv.add_service(service)
    return atv
