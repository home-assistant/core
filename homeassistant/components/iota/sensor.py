"""Support for IOTA wallet sensors."""
from datetime import timedelta

from homeassistant.const import CONF_NAME

from . import CONF_WALLETS, IotaDevice

ATTR_TESTNET = "testnet"
ATTR_URL = "url"

CONF_IRI = "iri"
CONF_SEED = "seed"
CONF_TESTNET = "testnet"

SCAN_INTERVAL = timedelta(minutes=3)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the IOTA sensor."""
    iota_config = discovery_info
    sensors = [
        IotaBalanceSensor(wallet, iota_config) for wallet in iota_config[CONF_WALLETS]
    ]

    sensors.append(IotaNodeSensor(iota_config=iota_config))

    add_entities(sensors)


class IotaBalanceSensor(IotaDevice):
    """Implement an IOTA sensor for displaying wallets balance."""

    def __init__(self, wallet_config, iota_config):
        """Initialize the sensor."""
        super().__init__(
            name=wallet_config[CONF_NAME],
            seed=wallet_config[CONF_SEED],
            iri=iota_config[CONF_IRI],
            is_testnet=iota_config[CONF_TESTNET],
        )
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} Balance"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "IOTA"

    def update(self):
        """Fetch new balance from IRI."""
        self._state = self.api.get_inputs()["totalBalance"]


class IotaNodeSensor(IotaDevice):
    """Implement an IOTA sensor for displaying attributes of node."""

    def __init__(self, iota_config):
        """Initialize the sensor."""
        super().__init__(
            name="Node Info",
            seed=None,
            iri=iota_config[CONF_IRI],
            is_testnet=iota_config[CONF_TESTNET],
        )
        self._state = None
        self._attr = {ATTR_URL: self.iri, ATTR_TESTNET: self.is_testnet}

    @property
    def name(self):
        """Return the name of the sensor."""
        return "IOTA Node"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attr

    def update(self):
        """Fetch new attributes IRI node."""
        node_info = self.api.get_node_info()
        self._state = node_info.get("appVersion")

        # convert values to raw string formats
        self._attr.update({k: str(v) for k, v in node_info.items()})
