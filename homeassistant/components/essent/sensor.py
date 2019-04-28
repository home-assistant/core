"""Support for Essent API."""

import xml.etree.ElementTree as ET

from pyessent import PyEssent

from homeassistant.const import ENERGY_KILO_WATT_HOUR, STATE_UNKNOWN
from homeassistant.helpers.entity import Entity

DOMAIN = 'essent'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Essent platform."""
    username = config['username']
    password = config['password']
    for meter in EssentBase(username, password).retrieve_meters():
        for tariff in ['L', 'N', 'H']:
            add_devices([EssentMeter(username, password, meter, tariff)])


class EssentBase():
    """Essent Base."""

    def __init__(self, username, password):
        """Initialize the Essent API."""
        self._essent = PyEssent(username, password)

    def get_session(self):
        """Return the active session."""
        return self._essent

    def retrieve_meters(self):
        """Retrieve the IDs of the meters used by Essent."""
        meters = []

        # Get customer details
        customer_details_request = self._essent.Customer.get_customer_details()

        # Parse our agreement ID
        agreement_id = ET.fromstring(customer_details_request.text) \
            .find('response') \
            .find('Partner') \
            .find('BusinessAgreements') \
            .find('BusinessAgreement') \
            .findtext('AgreementID')

        # Get business partner details
        business_partner_details_request = self._essent.Customer.get_business_partner_details(agreement_id)

        # Parse out our meters
        contracts = ET.fromstring(business_partner_details_request.text) \
            .find('response') \
            .find('Partner') \
            .find('BusinessAgreements') \
            .find('BusinessAgreement') \
            .find('Connections') \
            .find('Connection') \
            .find('Contracts') \
            .findall('Contract')

        for contract in contracts:
            meters.append(contract.findtext('ConnectEAN'))

        return meters


class EssentMeter(Entity):
    """Representation of Essent measurements."""

    def __init__(self, username, password, meter, tariff):
        """Initialize the sensor."""
        self._state = None
        self._username = username
        self._password = password
        self._meter = meter
        self._tariff = tariff
        self._meter_type = STATE_UNKNOWN
        self._meter_unit = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Essent {} ({})".format(self._meter_type, self._tariff)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._meter_unit and self._meter_unit.lower() == 'kwh':
            return ENERGY_KILO_WATT_HOUR

        return self._meter_unit

    def update(self):
        """Fetch the energy usage."""
        # Retrieve an authenticated session
        essent = EssentBase(self._username, self._password).get_session()

        # Read the meter
        meter_request = essent.Customer.get_meter_reading_history(
            self._meter, only_last_meter_reading=True)

        # Parse out into the root of our data
        info_base = ET.fromstring(meter_request.text) \
            .find('response') \
            .find('Installations') \
            .find('Installation')

        # Set meter type now that it's known
        self._meter_type = info_base.find('EnergyType').get('text')

        # Retrieve the current status
        registers = info_base.find('Meters') \
            .find('Meter') \
            .find('Registers') \
            .findall('Register')
        for register in registers:
            if (register.findtext('MeteringDirection') != 'LVR' or
                    register.findtext('TariffType') != self._tariff):
                continue

            # Set unit of measurement now that it's known
            self._meter_unit = register.findtext('MeasureUnit')
            self._state = register.find('MeterReadings') \
                .find('MeterReading') \
                .findtext('ReadingResultValue')
