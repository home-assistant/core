"""HA Elta tracking based on https://github.com/apo-mak/courier."""
import logging

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'c_Elta'
REQUIREMENTS = ['pycountry==17.1.8']
# DEPENDENCIES = []
ATTR_CODE = 'code'
DEFAULT_CODE = 'null'


def tracking(str):
    """"request for josn web post."""
    import requests

    tracking_number = str
    if len(tracking_number) != 13:
        result = ' the ', tracking_number, ' dose not seem like an ELTA \
        tracking number...'
        _LOGGER.error('Invalid key {0}. Key must be \
        13 characters'.format(tracking_number))
    else:
        headers = {'Cookie': 'lang=en'}
        r = requests.post(
            'http://www.elta-courier.gr/track.php',
            data={'number': tracking_number},
            headers=headers)
        t_result = r.json()['result'][tracking_number]['result']
        if t_result != 'wrong number':
            p_date = t_result[-1]['date']
            p_time = t_result[-1]['time']
            p_status = t_result[-1]['status']
            result = (p_date + " " + p_time + " " + p_status)
        else:
            result = ('wrong number')
        # Country_origin = pycountry.countries.lookup(tracking_number[-2:])
        # print ('Origin is: '+ Country_origin.name)
    return (result)


def setup(hass, config):
    """HA setup."""
    code = config[DOMAIN].get(ATTR_CODE, DEFAULT_CODE)
    wd = tracking(code)
    hass.states.set('c_Elta.trcode', wd)

    """Setup is called when Home Assistant is loading our component."""
    def handle_hello(call):
        name = call.data.get(ATTR_CODE, DEFAULT_CODE)
        wd = tracking(name)
        hass.states.set('c_Elta.trcode', wd)
    hass.services.register(DOMAIN, 'trcode', handle_hello)
    # Return boolean to indicate that initialization was successfully.
    return True
