from homeassistant.const import ENERGY_KILO_WATT_HOUR, STATE_UNKNOWN
from homeassistant.helpers.entity import Entity

import xml.etree.ElementTree as ET
import requests

DOMAIN = 'essent'

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Essent platform."""
    username = config['username']
    password = config['password']
    for meter in EssentBase(username, password).retrieve_meters():
        for tariff in ['L', 'N', 'H']:
            add_devices([EssentMeter(username, password, meter, tariff)])


class EssentBase():
    """Essent Base info."""

    def __init__(self, username, password):
        """Initialize the Essent API."""
        self._session = requests.session()

        # First, auth ourselves
        authentication_xml = """<AuthenticateUser>
        <request>
        <username><![CDATA[{}]]></username>
        <password><![CDATA[{}]]></password>
        <ControlParameters>
        <GetContracts>false</GetContracts>
        </ControlParameters></request>
        </AuthenticateUser>"""

        auth_request = self._session.post('https://api.essent.nl/selfservice/user/authenticateUser', data=authentication_xml.format(username, password))
        auth_request.raise_for_status()  # Throw exception if auth fails

    def get_session(self):
        return self._session

    def retrieve_meters(self):
        meters = []

        # Get customer details
        customer_details_request = self._session.get('https://api.essent.nl/selfservice/customer/getCustomerDetails', params={'GetContracts': 'false'})
        customer_details_request.raise_for_status()  # Throw exception if getting customer details fails

        # Parse our agreement ID
        agreement_id = ET.fromstring(customer_details_request.text).find('response').find('Partner').find('BusinessAgreements').find('BusinessAgreement').findtext('AgreementID')

        # Prepare retrieving business partner details
        business_partner_details_xml = """<GetBusinessPartnerDetails>
        <request>
        <AgreementID>{}</AgreementID>
        <OnlyActiveContracts>true</OnlyActiveContracts>
        </request>
        </GetBusinessPartnerDetails>"""

        # Get business partner details
        business_details_request = self._session.post('https://api.essent.nl/selfservice/customer/getBusinessPartnerDetails', data=business_partner_details_xml.format(agreement_id))
        business_details_request.raise_for_status()  # Throw exception if getting business partner details fails

        # Parse out our meters
        contracts = ET.fromstring(business_details_request.text).find('response').find('Partner').find('BusinessAgreements').find('BusinessAgreement').find('Connections').find('Connection').find('Contracts').findall('Contract')
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
        if self._meter_unit and self._meter_unit.lower() == "kwh":
            return ENERGY_KILO_WATT_HOUR

        return self._meter_unit

    def update(self):
        """Fetch the energy usage."""
        # Retrieve an authenticated session
        session = EssentBase(self._username, self._password).get_session()

        # Get current datetime according to server
        datetime_request = session.get('https://api.essent.nl/generic/getDateTime')
        datetime_request.raise_for_status()  # Throw exception if getting datetime fails
        datetime = ET.fromstring(datetime_request.text).findtext('Timestamp')

        # Prepare reading the meter
        meter_reading_xml = """<GetMeterReadingHistory>
        <request>
        <Installations>
        <Installation>
        <ConnectEAN>{}</ConnectEAN>
        </Installation>
        </Installations>
        <OnlyLastMeterReading>true</OnlyLastMeterReading><Period><StartDate>2000-01-01T00:00:00+02:00</StartDate><EndDate>{}</EndDate></Period></request>
        </GetMeterReadingHistory>"""

        # Request meter info
        meter_request = session.post('https://api.essent.nl/selfservice/customer/getMeterReadingHistory', data=meter_reading_xml.format(self._meter, datetime))
        meter_request.raise_for_status()  # Throw exception if getting meter history fails

        # Parse out into the root of our data
        info_base = ET.fromstring(meter_request.text).find('response').find('Installations').find('Installation')

        # Set meter type now that it's known
        self._meter_type = info_base.find('EnergyType').get('text')

        # Retrieve the current status
        for register in info_base.find('Meters').find('Meter').find('Registers').findall('Register'):
            if register.findtext('MeteringDirection') != 'LVR' or register.findtext('TariffType') != self._tariff:
                continue

            # Set unit of measurement now that it's known
            self._meter_unit = register.findtext('MeasureUnit')
            self._state = register.find('MeterReadings').find('MeterReading').findtext('ReadingResultValue')
