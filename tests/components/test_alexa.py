"""
tests.test_component_alexa
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Home Assistant Alexa component does what it should do.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
import json
from unittest.mock import patch

import requests

from homeassistant import bootstrap, const
import homeassistant.core as ha
from homeassistant.components import alexa, http

API_PASSWORD = "test1234"

# Somehow the socket that holds the default port does not get released
# when we close down HA in a different test case. Until I have figured
# out what is going on, let's run this test on a different port.
SERVER_PORT = 8119

API_URL = "http://127.0.0.1:{}{}".format(SERVER_PORT, alexa.API_ENDPOINT)

HA_HEADERS = {const.HTTP_HEADER_HA_AUTH: API_PASSWORD}

hass = None


@patch('homeassistant.components.http.util.get_local_ip',
       return_value='127.0.0.1')
def setUpModule(mock_get_local_ip):   # pylint: disable=invalid-name
    """ Initalizes a Home Assistant server. """
    global hass

    hass = ha.HomeAssistant()

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
         http.CONF_SERVER_PORT: SERVER_PORT}})

    bootstrap.setup_component(hass, alexa.DOMAIN, {
        'alexa': {
            'intents': {
                'WhereAreWeIntent': {
                    'speech': {
                        'type': 'plaintext',
                        'text':
                        """
                            {%- if is_state('device_tracker.paulus', 'home') and is_state('device_tracker.anne_therese', 'home') -%}
                                You are both home, you silly
                            {%- else -%}
                                Anne Therese is at {{ states("device_tracker.anne_therese") }} and Paulus is at {{ states("device_tracker.paulus") }}
                            {% endif %}
                        """,
                    }
                },
                'GetZodiacHoroscopeIntent': {
                    'speech': {
                        'type': 'plaintext',
                        'text': 'You told us your sign is {{ ZodiacSign }}.'
                    }
                }
            }
        }
    })

    hass.start()


def tearDownModule():   # pylint: disable=invalid-name
    """ Stops the Home Assistant server. """
    hass.stop()


def _req(data={}):
    return requests.post(API_URL, data=json.dumps(data), timeout=5,
                         headers=HA_HEADERS)


class TestAlexa(unittest.TestCase):
    """ Test Alexa. """

    def test_launch_request(self):
        data = {
            'version': '1.0',
            'session': {
                'new': True,
                'sessionId': 'amzn1.echo-api.session.0000000-0000-0000-0000-00000000000',
                'application': {
                    'applicationId': 'amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00ebe'
                },
                'attributes': {},
                'user': {
                    'userId': 'amzn1.account.AM3B00000000000000000000000'
                }
            },
            'request': {
                'type': 'LaunchRequest',
                'requestId': 'amzn1.echo-api.request.0000000-0000-0000-0000-00000000000',
                'timestamp': '2015-05-13T12:34:56Z'
            }
        }
        req = _req(data)
        self.assertEqual(200, req.status_code)
        resp = req.json()
        self.assertIn('outputSpeech', resp['response'])

    def test_intent_request_with_slots(self):
        data = {
            'version': '1.0',
            'session': {
                'new': False,
                'sessionId': 'amzn1.echo-api.session.0000000-0000-0000-0000-00000000000',
                'application': {
                    'applicationId': 'amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00ebe'
                },
                'attributes': {
                    'supportedHoroscopePeriods': {
                        'daily': True,
                        'weekly': False,
                        'monthly': False
                    }
                },
                'user': {
                    'userId': 'amzn1.account.AM3B00000000000000000000000'
                }
            },
            'request': {
                'type': 'IntentRequest',
                'requestId': ' amzn1.echo-api.request.0000000-0000-0000-0000-00000000000',
                'timestamp': '2015-05-13T12:34:56Z',
                'intent': {
                    'name': 'GetZodiacHoroscopeIntent',
                    'slots': {
                        'ZodiacSign': {
                            'name': 'ZodiacSign',
                            'value': 'virgo'
                        }
                    }
                }
            }
        }
        req = _req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get('response', {}).get('outputSpeech', {}).get('text')
        self.assertEqual('You told us your sign is virgo.', text)

    def test_intent_request_with_slots_but_no_value(self):
        data = {
            'version': '1.0',
            'session': {
                'new': False,
                'sessionId': 'amzn1.echo-api.session.0000000-0000-0000-0000-00000000000',
                'application': {
                    'applicationId': 'amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00ebe'
                },
                'attributes': {
                    'supportedHoroscopePeriods': {
                        'daily': True,
                        'weekly': False,
                        'monthly': False
                    }
                },
                'user': {
                    'userId': 'amzn1.account.AM3B00000000000000000000000'
                }
            },
            'request': {
                'type': 'IntentRequest',
                'requestId': ' amzn1.echo-api.request.0000000-0000-0000-0000-00000000000',
                'timestamp': '2015-05-13T12:34:56Z',
                'intent': {
                    'name': 'GetZodiacHoroscopeIntent',
                    'slots': {
                        'ZodiacSign': {
                            'name': 'ZodiacSign',
                        }
                    }
                }
            }
        }
        req = _req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get('response', {}).get('outputSpeech', {}).get('text')
        self.assertEqual('You told us your sign is .', text)

    def test_intent_request_without_slots(self):
        data = {
            'version': '1.0',
            'session': {
                'new': False,
                'sessionId': 'amzn1.echo-api.session.0000000-0000-0000-0000-00000000000',
                'application': {
                    'applicationId': 'amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00ebe'
                },
                'attributes': {
                    'supportedHoroscopePeriods': {
                        'daily': True,
                        'weekly': False,
                        'monthly': False
                    }
                },
                'user': {
                    'userId': 'amzn1.account.AM3B00000000000000000000000'
                }
            },
            'request': {
                'type': 'IntentRequest',
                'requestId': ' amzn1.echo-api.request.0000000-0000-0000-0000-00000000000',
                'timestamp': '2015-05-13T12:34:56Z',
                'intent': {
                    'name': 'WhereAreWeIntent',
                }
            }
        }
        req = _req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get('response', {}).get('outputSpeech', {}).get('text')

        self.assertEqual('Anne Therese is at unknown and Paulus is at unknown', text)

        hass.states.set('device_tracker.paulus', 'home')
        hass.states.set('device_tracker.anne_therese', 'home')

        req = _req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get('response', {}).get('outputSpeech', {}).get('text')
        self.assertEqual('You are both home, you silly', text)

    def test_session_ended_request(self):
        data = {
            'version': '1.0',
            'session': {
                'new': False,
                'sessionId': 'amzn1.echo-api.session.0000000-0000-0000-0000-00000000000',
                'application': {
                    'applicationId': 'amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00ebe'
                },
                'attributes': {
                    'supportedHoroscopePeriods': {
                      'daily': True,
                      'weekly': False,
                      'monthly': False
                    }
                },
                'user': {
                    'userId': 'amzn1.account.AM3B00000000000000000000000'
                }
            },
            'request': {
                'type': 'SessionEndedRequest',
                'requestId': 'amzn1.echo-api.request.0000000-0000-0000-0000-00000000000',
                'timestamp': '2015-05-13T12:34:56Z',
                'reason': 'USER_INITIATED'
            }
        }

        req = _req(data)
        self.assertEqual(200, req.status_code)
        self.assertEqual('', req.text)
