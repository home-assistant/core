"""
homeassistant.components.sensor.bitcoin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bitcoin information service that uses blockchain.info and its online wallet.

Configuration:

You need to enable the API access for your online wallet to get the balance.
To do that log in and move to 'Account Setting', choose 'IP Restrictions', and
check 'Enable Api Access'. You will get an email message from blockchain.info
where you must authorize the API access.

To use the Bitcoin sensor you will need to add something like the following
to your config/configuration.yaml

sensor:
  platform: bitcoin
  wallet: 'YOUR WALLET_ID'
  password: YOUR_ACCOUNT_PASSWORD
  currency: YOUR CURRENCY
  display_options:
    - exchangerate
    - trade_volume_btc
    - miners_revenue_usd
    - btc_mined
    - trade_volume_usd
    - difficulty
    - minutes_between_blocks
    - number_of_transactions
    - hash_rate
    - timestamp
    - mined_blocks
    - blocks_size
    - total_fees_btc
    - total_btc_sent
    - estimated_btc_sent
    - total_btc
    - total_blocks
    - next_retarget
    - estimated_transaction_volume_usd
    - miners_revenue_btc
    - market_price_usd

Variables:

wallet
*Optional
This is your wallet identifier from https://blockchain.info to access the
online wallet.

password
*Optional
Password your your online wallet.

currency
*Optional
The currency to exchange to, eg. CHF, USD, EUR,etc. Default is USD.

display_options
*Optional
An array specifying the variables to display.

These are the variables for the display_options array. See the configuration
example above for a list of all available variables.
"""
import logging
from datetime import timedelta

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity


REQUIREMENTS = ['blockchain==1.1.2']
_LOGGER = logging.getLogger(__name__)
OPTION_TYPES = {
    'wallet': ['Wallet balance', 'BTC'],
    'exchangerate': ['Exchange rate (1 BTC)', ''],
    'trade_volume_btc': ['Trade volume', 'BTC'],
    'miners_revenue_usd': ['Miners revenue', 'USD'],
    'btc_mined': ['Mined', 'BTC'],
    'trade_volume_usd': ['Trade volume', 'USD'],
    'difficulty': ['Difficulty', ''],
    'minutes_between_blocks': ['Time between Blocks', 'min'],
    'number_of_transactions': ['No. of Transactions', ''],
    'hash_rate': ['Hash rate', 'PH/s'],
    'timestamp': ['Timestamp', ''],
    'mined_blocks': ['Minded Blocks', ''],
    'blocks_size': ['Block size', ''],
    'total_fees_btc': ['Total fees', 'BTC'],
    'total_btc_sent': ['Total sent', 'BTC'],
    'estimated_btc_sent': ['Estimated sent', 'BTC'],
    'total_btc': ['Total', 'BTC'],
    'total_blocks': ['Total Blocks', ''],
    'next_retarget': ['Next retarget', ''],
    'estimated_transaction_volume_usd': ['Est. Transaction volume', 'USD'],
    'miners_revenue_btc': ['Miners revenue', 'BTC'],
    'market_price_usd': ['Market price', 'USD']
}

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the Bitcoin sensor. """

    try:
        from blockchain.wallet import Wallet
        from blockchain import exchangerates, exceptions

    except ImportError:
        _LOGGER.exception(
            "Unable to import blockchain. "
            "Did you maybe not install the 'blockchain' package?")

        return False

    wallet_id = config.get('wallet', None)
    password = config.get('password', None)
    currency = config.get('currency', 'USD')

    if currency not in exchangerates.get_ticker():
        _LOGGER.error('Currency "%s" is not available. Using "USD".', currency)
        currency = 'USD'

    wallet = Wallet(wallet_id, password)

    try:
        wallet.get_balance()
    except exceptions.APIException as error:
        _LOGGER.error(error)
        wallet = None

    data = BitcoinData()
    dev = []
    if wallet is not None and password is not None:
        dev.append(BitcoinSensor(data, 'wallet', currency, wallet))

    for variable in config['display_options']:
        if variable not in OPTION_TYPES:
            _LOGGER.error('Option type: "%s" does not exist', variable)
        else:
            dev.append(BitcoinSensor(data, variable, currency))

    add_devices(dev)


# pylint: disable=too-few-public-methods
class BitcoinSensor(Entity):
    """ Implements a Bitcoin sensor. """

    def __init__(self, data, option_type, currency, wallet=''):
        self.data = data
        self._name = OPTION_TYPES[option_type][0]
        self._unit_of_measurement = OPTION_TYPES[option_type][1]
        self._currency = currency
        self._wallet = wallet
        self.type = option_type
        self._state = None
        self.update()

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    # pylint: disable=too-many-branches
    def update(self):
        """ Gets the latest data and updates the states. """

        self.data.update()
        stats = self.data.stats
        ticker = self.data.ticker

        # pylint: disable=no-member
        if self.type == 'wallet' and self._wallet is not None:
            self._state = '{0:.8f}'.format(self._wallet.get_balance() *
                                           0.00000001)
        elif self.type == 'exchangerate':
            self._state = ticker[self._currency].p15min
            self._unit_of_measurement = self._currency
        elif self.type == 'trade_volume_btc':
            self._state = '{0:.1f}'.format(stats.trade_volume_btc)
        elif self.type == 'miners_revenue_usd':
            self._state = '{0:.0f}'.format(stats.miners_revenue_usd)
        elif self.type == 'btc_mined':
            self._state = '{}'.format(stats.btc_mined * 0.00000001)
        elif self.type == 'trade_volume_usd':
            self._state = '{0:.1f}'.format(stats.trade_volume_usd)
        elif self.type == 'difficulty':
            self._state = '{0:.0f}'.format(stats.difficulty)
        elif self.type == 'minutes_between_blocks':
            self._state = '{0:.2f}'.format(stats.minutes_between_blocks)
        elif self.type == 'number_of_transactions':
            self._state = '{}'.format(stats.number_of_transactions)
        elif self.type == 'hash_rate':
            self._state = '{0:.1f}'.format(stats.hash_rate * 0.000001)
        elif self.type == 'timestamp':
            self._state = stats.timestamp
        elif self.type == 'mined_blocks':
            self._state = '{}'.format(stats.mined_blocks)
        elif self.type == 'blocks_size':
            self._state = '{0:.1f}'.format(stats.blocks_size)
        elif self.type == 'total_fees_btc':
            self._state = '{0:.2f}'.format(stats.total_fees_btc * 0.00000001)
        elif self.type == 'total_btc_sent':
            self._state = '{0:.2f}'.format(stats.total_btc_sent * 0.00000001)
        elif self.type == 'estimated_btc_sent':
            self._state = '{0:.2f}'.format(stats.estimated_btc_sent *
                                           0.00000001)
        elif self.type == 'total_btc':
            self._state = '{0:.2f}'.format(stats.total_btc * 0.00000001)
        elif self.type == 'total_blocks':
            self._state = '{0:.2f}'.format(stats.total_blocks)
        elif self.type == 'next_retarget':
            self._state = '{0:.2f}'.format(stats.next_retarget)
        elif self.type == 'estimated_transaction_volume_usd':
            self._state = '{0:.2f}'.format(
                stats.estimated_transaction_volume_usd)
        elif self.type == 'miners_revenue_btc':
            self._state = '{0:.1f}'.format(stats.miners_revenue_btc *
                                           0.00000001)
        elif self.type == 'market_price_usd':
            self._state = '{0:.2f}'.format(stats.market_price_usd)


class BitcoinData(object):
    """ Gets the latest data and updates the states. """

    def __init__(self):
        self.stats = None
        self.ticker = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from blockchain.info. """

        from blockchain import statistics, exchangerates

        self.stats = statistics.get()
        self.ticker = exchangerates.get_ticker()
