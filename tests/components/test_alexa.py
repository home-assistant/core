"""The tests for the Alexa component."""
# pylint: disable=protected-access,too-many-public-methods
import json
import time
import unittest

import requests

from homeassistant import bootstrap, const
from homeassistant.components import alexa, http

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
API_URL = "http://127.0.0.1:{}{}".format(SERVER_PORT, alexa.API_ENDPOINT)
HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

SESSION_ID = 'amzn1.echo-api.session.0000000-0000-0000-0000-00000000000'
APPLICATION_ID = 'amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00ebe'
REQUEST_ID = 'amzn1.echo-api.request.0000000-0000-0000-0000-00000000000'

hass = None
calls = []


def setUpModule():   # pylint: disable=invalid-name
    """Initialize a Home Assistant server for testing this module."""
    global hass

    hass = get_test_home_assistant()

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
         http.CONF_SERVER_PORT: SERVER_PORT}})

    hass.services.register('test', 'alexa', lambda call: calls.append(call))

    bootstrap.setup_component(hass, alexa.DOMAIN, {
        # Key is here to verify we allow other keys in config too
        'homeassistant': {},
        'alexa': {
            'intents': {
                'WhereAreWeIntent': {
                    'speech': {
                        'type': 'plaintext',
                        'text':
                        """
                            {%- if is_state('device_tracker.paulus', 'home')
                                   and is_state('device_tracker.anne_therese',
                                                'home') -%}
                                You are both home, you silly
                            {%- else -%}
                                Anne Therese is at {{
                                    states("device_tracker.anne_therese")
                                }} and Paulus is at {{
                                    states("device_tracker.paulus")
                                }}
                            {% endif %}
                        """,
                    }
                },
                'GetZodiacHoroscopeIntent': {
                    'speech': {
                        'type': 'plaintext',
                        'text': 'You told us your sign is {{ ZodiacSign }}.',
                    }
                },
                'CallServiceIntent': {
                    'speech': {
                        'type': 'plaintext',
                        'text': 'Service called',
                    },
                    'action': {
                        'service': 'test.alexa',
                        'data_template': {
                            'hello': '{{ ZodiacSign }}'
                        },
                        'entity_id': 'switch.test',
                    }
                }
            }
        }
    })

    hass.start()
    time.sleep(0.05)


def tearDownModule():   # pylint: disable=invalid-name
    """Stop the Home Assistant server."""
    hass.stop()


def _req(data={}):
    return requests.post(API_URL, data=json.dumps(data), timeout=5,
                         headers=HA_HEADERS)


class TestAlexa(unittest.TestCase):
    """Test Alexa."""

    def tearDown(self):
        """Stop everything that was started."""
        hass.block_till_done()

    def test_launch_request(self):
        """Test the launch of a request."""
        data = {
            'version': '1.0',
            'session': {
                'new': True,
                'sessionId': SESSION_ID,
                'application': {
                    'applicationId': APPLICATION_ID
                },
                'attributes': {},
                'user': {
                    'userId': 'amzn1.account.AM3B00000000000000000000000'
                }
            },
            'request': {
                'type': 'LaunchRequest',
                'requestId': REQUEST_ID,
                'timestamp': '2015-05-13T12:34:56Z'
            }
        }
        req = _req(data)
        self.assertEqual(200, req.status_code)
        resp = req.json()
        self.assertIn('outputSpeech', resp['response'])

    def test_intent_request_with_slots(self):
        """Test a request with slots."""
        data = {
            'version': '1.0',
            'session': {
                'new': False,
                'sessionId': SESSION_ID,
                'application': {
                    'applicationId': APPLICATION_ID
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
                'requestId': REQUEST_ID,
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
        text = req.json().get('response', {}).get('outputSpeech',
                                                  {}).get('text')
        self.assertEqual('You told us your sign is virgo.', text)

    def test_intent_request_with_slots_but_no_value(self):
        """Test a request with slots but no value."""
        data = {
            'version': '1.0',
            'session': {
                'new': False,
                'sessionId': SESSION_ID,
                'application': {
                    'applicationId': APPLICATION_ID
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
                'requestId': REQUEST_ID,
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
        text = req.json().get('response', {}).get('outputSpeech',
                                                  {}).get('text')
        self.assertEqual('You told us your sign is .', text)

    def test_intent_request_without_slots(self):
        """Test a request without slots."""
        data = {
            'version': '1.0',
            'session': {
                'new': False,
                'sessionId': SESSION_ID,
                'application': {
                    'applicationId': APPLICATION_ID
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
                'requestId': REQUEST_ID,
                'timestamp': '2015-05-13T12:34:56Z',
                'intent': {
                    'name': 'WhereAreWeIntent',
                }
            }
        }
        req = _req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get('response', {}).get('outputSpeech',
                                                  {}).get('text')

        self.assertEqual('Anne Therese is at unknown and Paulus is at unknown',
                         text)

        hass.states.set('device_tracker.paulus', 'home')
        hass.states.set('device_tracker.anne_therese', 'home')

        req = _req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get('response', {}).get('outputSpeech',
                                                  {}).get('text')
        self.assertEqual('You are both home, you silly', text)

    def test_intent_request_calling_service(self):
        """Test a request for calling a service."""
        data = {
            'version': '1.0',
            'session': {
                'new': False,
                'sessionId': SESSION_ID,
                'application': {
                    'applicationId': APPLICATION_ID
                },
                'attributes': {},
                'user': {
                    'userId': 'amzn1.account.AM3B00000000000000000000000'
                }
            },
            'request': {
                'type': 'IntentRequest',
                'requestId': REQUEST_ID,
                'timestamp': '2015-05-13T12:34:56Z',
                'intent': {
                    'name': 'CallServiceIntent',
                    'slots': {
                        'ZodiacSign': {
                            'name': 'ZodiacSign',
                            'value': 'virgo',
                        }
                    }
                }
            }
        }
        call_count = len(calls)
        req = _req(data)
        self.assertEqual(200, req.status_code)
        self.assertEqual(call_count + 1, len(calls))
        call = calls[-1]
        self.assertEqual('test', call.domain)
        self.assertEqual('alexa', call.service)
        self.assertEqual(['switch.test'], call.data.get('entity_id'))
        self.assertEqual('virgo', call.data.get('hello'))

    def test_session_ended_request(self):
        """Test the request for ending the session."""
        data = {
            'version': '1.0',
            'session': {
                'new': False,
                'sessionId': SESSION_ID,
                'application': {
                    'applicationId': APPLICATION_ID
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
                'requestId': REQUEST_ID,
                'timestamp': '2015-05-13T12:34:56Z',
                'reason': 'USER_INITIATED'
            }
        }

        req = _req(data)
        self.assertEqual(200, req.status_code)
        self.assertEqual('', req.text)
