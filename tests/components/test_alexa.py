"""The tests for the Alexa component."""
# pylint: disable=protected-access
import json
import datetime
import unittest

import requests

from homeassistant.core import callback
from homeassistant import bootstrap, const
from homeassistant.components import alexa, http

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
BASE_API_URL = "http://127.0.0.1:{}".format(SERVER_PORT)
INTENTS_API_URL = "{}{}".format(BASE_API_URL, alexa.INTENTS_API_ENDPOINT)

HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

SESSION_ID = "amzn1.echo-api.session.0000000-0000-0000-0000-00000000000"
APPLICATION_ID = "amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00ebe"
REQUEST_ID = "amzn1.echo-api.request.0000000-0000-0000-0000-00000000000"

# pylint: disable=invalid-name
hass = None
calls = []

NPR_NEWS_MP3_URL = "https://pd.npr.org/anon.npr-mp3/npr/news/newscast.mp3"

# 2016-10-10T19:51:42+00:00
STATIC_TIME = datetime.datetime.utcfromtimestamp(1476129102)


# pylint: disable=invalid-name
def setUpModule():
    """Initialize a Home Assistant server for testing this module."""
    global hass

    hass = get_test_home_assistant()

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                       http.CONF_SERVER_PORT: SERVER_PORT}})

    @callback
    def mock_service(call):
        calls.append(call)

    hass.services.register("test", "alexa", mock_service)

    bootstrap.setup_component(hass, alexa.DOMAIN, {
        # Key is here to verify we allow other keys in config too
        "homeassistant": {},
        "alexa": {
            "flash_briefings": {
                "weather": [
                    {"title": "Weekly forecast",
                     "text": "This week it will be sunny.",
                     "date": "2016-10-09T19:51:42.0Z"},
                    {"title": "Current conditions",
                     "text": "Currently it is 80 degrees fahrenheit.",
                     "date": STATIC_TIME}
                ],
                "news_audio": {
                    "title": "NPR",
                    "audio": NPR_NEWS_MP3_URL,
                    "display_url": "https://npr.org",
                    "date": STATIC_TIME,
                    "uid": "uuid"
                }
            },
            "intents": {
                "WhereAreWeIntent": {
                    "speech": {
                        "type": "plaintext",
                        "text":
                        """
                            {%- if is_state("device_tracker.paulus", "home")
                                   and is_state("device_tracker.anne_therese",
                                                "home") -%}
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
                "GetZodiacHoroscopeIntent": {
                    "speech": {
                        "type": "plaintext",
                        "text": "You told us your sign is {{ ZodiacSign }}.",
                    }
                },
                "CallServiceIntent": {
                    "speech": {
                        "type": "plaintext",
                        "text": "Service called",
                    },
                    "action": {
                        "service": "test.alexa",
                        "data_template": {
                            "hello": "{{ ZodiacSign }}"
                        },
                        "entity_id": "switch.test",
                    }
                }
            }
        }
    })

    hass.start()


# pylint: disable=invalid-name
def tearDownModule():
    """Stop the Home Assistant server."""
    hass.stop()


def _intent_req(data={}):
    return requests.post(INTENTS_API_URL, data=json.dumps(data), timeout=5,
                         headers=HA_HEADERS)


def _flash_briefing_req(briefing_id=None):
    url_format = "{}/api/alexa/flash_briefings/{}"
    FLASH_BRIEFING_API_URL = url_format.format(BASE_API_URL,
                                               briefing_id)
    return requests.get(FLASH_BRIEFING_API_URL, timeout=5,
                        headers=HA_HEADERS)


class TestAlexa(unittest.TestCase):
    """Test Alexa."""

    def tearDown(self):
        """Stop everything that was started."""
        hass.block_till_done()

    def test_intent_launch_request(self):
        """Test the launch of a request."""
        data = {
            "version": "1.0",
            "session": {
                "new": True,
                "sessionId": SESSION_ID,
                "application": {
                    "applicationId": APPLICATION_ID
                },
                "attributes": {},
                "user": {
                    "userId": "amzn1.account.AM3B00000000000000000000000"
                }
            },
            "request": {
                "type": "LaunchRequest",
                "requestId": REQUEST_ID,
                "timestamp": "2015-05-13T12:34:56Z"
            }
        }
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        resp = req.json()
        self.assertIn("outputSpeech", resp["response"])

    def test_intent_request_with_slots(self):
        """Test a request with slots."""
        data = {
            "version": "1.0",
            "session": {
                "new": False,
                "sessionId": SESSION_ID,
                "application": {
                    "applicationId": APPLICATION_ID
                },
                "attributes": {
                    "supportedHoroscopePeriods": {
                        "daily": True,
                        "weekly": False,
                        "monthly": False
                    }
                },
                "user": {
                    "userId": "amzn1.account.AM3B00000000000000000000000"
                }
            },
            "request": {
                "type": "IntentRequest",
                "requestId": REQUEST_ID,
                "timestamp": "2015-05-13T12:34:56Z",
                "intent": {
                    "name": "GetZodiacHoroscopeIntent",
                    "slots": {
                        "ZodiacSign": {
                            "name": "ZodiacSign",
                            "value": "virgo"
                        }
                    }
                }
            }
        }
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("response", {}).get("outputSpeech",
                                                  {}).get("text")
        self.assertEqual("You told us your sign is virgo.", text)

    def test_intent_request_with_slots_but_no_value(self):
        """Test a request with slots but no value."""
        data = {
            "version": "1.0",
            "session": {
                "new": False,
                "sessionId": SESSION_ID,
                "application": {
                    "applicationId": APPLICATION_ID
                },
                "attributes": {
                    "supportedHoroscopePeriods": {
                        "daily": True,
                        "weekly": False,
                        "monthly": False
                    }
                },
                "user": {
                    "userId": "amzn1.account.AM3B00000000000000000000000"
                }
            },
            "request": {
                "type": "IntentRequest",
                "requestId": REQUEST_ID,
                "timestamp": "2015-05-13T12:34:56Z",
                "intent": {
                    "name": "GetZodiacHoroscopeIntent",
                    "slots": {
                        "ZodiacSign": {
                            "name": "ZodiacSign",
                        }
                    }
                }
            }
        }
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("response", {}).get("outputSpeech",
                                                  {}).get("text")
        self.assertEqual("You told us your sign is .", text)

    def test_intent_request_without_slots(self):
        """Test a request without slots."""
        data = {
            "version": "1.0",
            "session": {
                "new": False,
                "sessionId": SESSION_ID,
                "application": {
                    "applicationId": APPLICATION_ID
                },
                "attributes": {
                    "supportedHoroscopePeriods": {
                        "daily": True,
                        "weekly": False,
                        "monthly": False
                    }
                },
                "user": {
                    "userId": "amzn1.account.AM3B00000000000000000000000"
                }
            },
            "request": {
                "type": "IntentRequest",
                "requestId": REQUEST_ID,
                "timestamp": "2015-05-13T12:34:56Z",
                "intent": {
                    "name": "WhereAreWeIntent",
                }
            }
        }
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("response", {}).get("outputSpeech",
                                                  {}).get("text")

        self.assertEqual("Anne Therese is at unknown and Paulus is at unknown",
                         text)

        hass.states.set("device_tracker.paulus", "home")
        hass.states.set("device_tracker.anne_therese", "home")

        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("response", {}).get("outputSpeech",
                                                  {}).get("text")
        self.assertEqual("You are both home, you silly", text)

    def test_intent_request_calling_service(self):
        """Test a request for calling a service."""
        data = {
            "version": "1.0",
            "session": {
                "new": False,
                "sessionId": SESSION_ID,
                "application": {
                    "applicationId": APPLICATION_ID
                },
                "attributes": {},
                "user": {
                    "userId": "amzn1.account.AM3B00000000000000000000000"
                }
            },
            "request": {
                "type": "IntentRequest",
                "requestId": REQUEST_ID,
                "timestamp": "2015-05-13T12:34:56Z",
                "intent": {
                    "name": "CallServiceIntent",
                    "slots": {
                        "ZodiacSign": {
                            "name": "ZodiacSign",
                            "value": "virgo",
                        }
                    }
                }
            }
        }
        call_count = len(calls)
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        self.assertEqual(call_count + 1, len(calls))
        call = calls[-1]
        self.assertEqual("test", call.domain)
        self.assertEqual("alexa", call.service)
        self.assertEqual(["switch.test"], call.data.get("entity_id"))
        self.assertEqual("virgo", call.data.get("hello"))

    def test_intent_session_ended_request(self):
        """Test the request for ending the session."""
        data = {
            "version": "1.0",
            "session": {
                "new": False,
                "sessionId": SESSION_ID,
                "application": {
                    "applicationId": APPLICATION_ID
                },
                "attributes": {
                    "supportedHoroscopePeriods": {
                        "daily": True,
                        "weekly": False,
                        "monthly": False
                    }
                },
                "user": {
                    "userId": "amzn1.account.AM3B00000000000000000000000"
                }
            },
            "request": {
                "type": "SessionEndedRequest",
                "requestId": REQUEST_ID,
                "timestamp": "2015-05-13T12:34:56Z",
                "reason": "USER_INITIATED"
            }
        }

        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        self.assertEqual("", req.text)

    def test_flash_briefing_invalid_id(self):
        """Test an invalid Flash Briefing ID."""
        req = _flash_briefing_req()
        self.assertEqual(404, req.status_code)
        self.assertEqual("", req.text)

    def test_flash_briefing_date_from_str(self):
        """Test the response has a valid date parsed from string."""
        req = _flash_briefing_req("weather")
        self.assertEqual(200, req.status_code)
        self.assertEqual(req.json()[0].get(alexa.ATTR_UPDATE_DATE),
                         "2016-10-09T19:51:42.0Z")

    def test_flash_briefing_date_from_datetime(self):
        """Test the response has a valid date from a datetime object."""
        req = _flash_briefing_req("weather")
        self.assertEqual(200, req.status_code)
        self.assertEqual(req.json()[1].get(alexa.ATTR_UPDATE_DATE),
                         '2016-10-10T19:51:42.0Z')

    def test_flash_briefing_valid(self):
        """Test the response is valid."""
        data = [{
            "titleText": "NPR",
            "redirectionURL": "https://npr.org",
            "streamUrl": NPR_NEWS_MP3_URL,
            "mainText": "",
            "uid": "uuid",
            "updateDate": '2016-10-10T19:51:42.0Z'
        }]

        req = _flash_briefing_req("news_audio")
        self.assertEqual(200, req.status_code)
        response = req.json()
        self.assertEqual(response, data)
