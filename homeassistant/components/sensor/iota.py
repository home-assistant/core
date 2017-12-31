import logging

from homeassistant.components.iota import DOMAIN as IOTA_DOMAIN, IotaDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['iota']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the IOTA sensor."""

    # Add sensors for wallet balance
    iota_config = hass.data[IOTA_DOMAIN]
    balance_sensors = [IotaBalanceSensor(wallet, iota_config)
                       for wallet in iota_config['wallets']]
    add_devices(balance_sensors)

    # Add sensor for node information
    add_devices([IotaNodeSensor(iota_config=iota_config)])


class IotaBalanceSensor(IotaDevice):
    """Implement an IOTA sensor for displaying wallets balance."""

    def __init__(self, wallet_config, iota_config):
        """Initialize the sensor."""

        super().__init__(name=wallet_config['name'],
                         seed=wallet_config['seed'],
                         iri=iota_config['iri'],
                         is_testnet=iota_config['is_testnet'])
        self._state = 0

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} Balance'.format(self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'IOTA'

    def update(self):
        """Fetch new balance from IRI."""
        self._state = self.api.get_inputs()['totalBalance']


class IotaNodeSensor(IotaDevice):
    """Implement an IOTA sensor for displaying attributes of node."""

    def __init__(self, iota_config):
        """Initialize the sensor."""

        super().__init__(name='Node Info', seed=None, iri=iota_config['iri'],
                         is_testnet=iota_config['is_testnet'])
        self._state = ""
        self._attr = dict()

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'IOTA Node'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attr

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ''

    def update(self):
        """Fetch new attribures IRI node."""
        node_info = self.api.get_node_info()
        self._state = node_info.get('appVersion')
        # convert values to raw string formats
        self._attr = {k: str(v) for k, v in node_info.items()}
