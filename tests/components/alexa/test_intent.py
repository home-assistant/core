"""The tests for the Alexa component."""
# pylint: disable=protected-access
import asyncio
import json

import pytest

from homeassistant.core import callback
from homeassistant.setup import async_setup_component
from homeassistant.components import alexa
from homeassistant.components.alexa import intent

SESSION_ID = "amzn1.echo-api.session.0000000-0000-0000-0000-00000000000"
APPLICATION_ID = "amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00ebe"
REQUEST_ID = "amzn1.echo-api.request.0000000-0000-0000-0000-00000000000"
AUTHORITY_ID = "amzn1.er-authority.000000-d0ed-0000-ad00-000000d00ebe.ZODIAC"
BUILTIN_AUTH_ID = "amzn1.er-authority.000000-d0ed-0000-ad00-000000d00ebe.TEST"

# pylint: disable=invalid-name
calls = []

NPR_NEWS_MP3_URL = "https://pd.npr.org/anon.npr-mp3/npr/news/newscast.mp3"


@pytest.fixture
def alexa_client(loop, hass, test_client):
    """Initialize a Home Assistant server for testing this module."""
    @callback
    def mock_service(call):
        calls.append(call)

    hass.services.async_register("test", "alexa", mock_service)

    assert loop.run_until_complete(async_setup_component(hass, alexa.DOMAIN, {
        # Key is here to verify we allow other keys in config too
        "homeassistant": {},
    }))
    assert loop.run_until_complete(async_setup_component(
        hass, 'intent_script', {
            'intent_script': {
                "WhereAreWeIntent": {
                    "speech": {
                        "type": "plain",
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
                        "type": "plain",
                        "text": "You told us your sign is {{ ZodiacSign }}.",
                    }
                },
                "AMAZON.PlaybackAction<object@MusicCreativeWork>": {
                    "speech": {
                        "type": "plain",
                        "text": "Playing {{ object_byArtist_name }}.",
                    }
                },
                "CallServiceIntent": {
                    "speech": {
                        "type": "plain",
                        "text": "Service called for {{ ZodiacSign }}",
                    },
                    "card": {
                        "type": "simple",
                        "title": "Card title for {{ ZodiacSign }}",
                        "content": "Card content: {{ ZodiacSign }}",
                    },
                    "action": {
                        "service": "test.alexa",
                        "data_template": {
                            "hello": "{{ ZodiacSign }}"
                        },
                        "entity_id": "switch.test",
                    }
                },
                APPLICATION_ID: {
                    "speech": {
                        "type": "plain",
                        "text": "LaunchRequest has been received.",
                    }
                },
            }
        }))
    return loop.run_until_complete(test_client(hass.http.app))


def _intent_req(client, data=None):
    return client.post(intent.INTENTS_API_ENDPOINT,
                       data=json.dumps(data or {}),
                       headers={'content-type': 'application/json'})


@asyncio.coroutine
def test_intent_launch_request(alexa_client):
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
    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    data = yield from req.json()
    text = data.get("response", {}).get("outputSpeech",
                                        {}).get("text")
    assert text == "LaunchRequest has been received."


@asyncio.coroutine
def test_intent_launch_request_not_configured(alexa_client):
    """Test the launch of a request."""
    data = {
        "version": "1.0",
        "session": {
            "new": True,
            "sessionId": SESSION_ID,
            "application": {
                "applicationId":
                    'amzn1.echo-sdk-ams.app.000000-d0ed-0000-ad00-000000d00000'
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
    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    data = yield from req.json()
    text = data.get("response", {}).get("outputSpeech",
                                        {}).get("text")
    assert text == "This intent is not yet configured within Home Assistant."


@asyncio.coroutine
def test_intent_request_with_slots(alexa_client):
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
    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    data = yield from req.json()
    text = data.get("response", {}).get("outputSpeech",
                                        {}).get("text")
    assert text == "You told us your sign is virgo."


@asyncio.coroutine
def test_intent_request_with_slots_and_synonym_resolution(alexa_client):
    """Test a request with slots and a name synonym."""
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
                        "value": "V zodiac",
                        "resolutions": {
                            "resolutionsPerAuthority": [
                                {
                                    "authority": AUTHORITY_ID,
                                    "status": {
                                        "code": "ER_SUCCESS_MATCH"
                                    },
                                    "values": [
                                        {
                                            "value": {
                                                "name": "Virgo"
                                            }
                                        }
                                    ]
                                },
                                {
                                    "authority": BUILTIN_AUTH_ID,
                                    "status": {
                                        "code": "ER_SUCCESS_NO_MATCH"
                                    },
                                    "values": [
                                        {
                                            "value": {
                                                "name": "Test"
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    data = yield from req.json()
    text = data.get("response", {}).get("outputSpeech",
                                        {}).get("text")
    assert text == "You told us your sign is Virgo."


@asyncio.coroutine
def test_intent_request_with_slots_and_multi_synonym_resolution(alexa_client):
    """Test a request with slots and multiple name synonyms."""
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
                        "value": "V zodiac",
                        "resolutions": {
                            "resolutionsPerAuthority": [
                                {
                                    "authority": AUTHORITY_ID,
                                    "status": {
                                        "code": "ER_SUCCESS_MATCH"
                                    },
                                    "values": [
                                        {
                                            "value": {
                                                "name": "Virgo"
                                            }
                                        }
                                    ]
                                },
                                {
                                    "authority": BUILTIN_AUTH_ID,
                                    "status": {
                                        "code": "ER_SUCCESS_MATCH"
                                    },
                                    "values": [
                                        {
                                            "value": {
                                                "name": "Test"
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    data = yield from req.json()
    text = data.get("response", {}).get("outputSpeech",
                                        {}).get("text")
    assert text == "You told us your sign is V zodiac."


@asyncio.coroutine
def test_intent_request_with_slots_but_no_value(alexa_client):
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
                        "name": "ZodiacSign"
                    }
                }
            }
        }
    }
    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    data = yield from req.json()
    text = data.get("response", {}).get("outputSpeech",
                                        {}).get("text")
    assert text == "You told us your sign is ."


@asyncio.coroutine
def test_intent_request_without_slots(hass, alexa_client):
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
    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    json = yield from req.json()
    text = json.get("response", {}).get("outputSpeech",
                                        {}).get("text")

    assert text == "Anne Therese is at unknown and Paulus is at unknown"

    hass.states.async_set("device_tracker.paulus", "home")
    hass.states.async_set("device_tracker.anne_therese", "home")

    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    json = yield from req.json()
    text = json.get("response", {}).get("outputSpeech",
                                        {}).get("text")
    assert text == "You are both home, you silly"


@asyncio.coroutine
def test_intent_request_calling_service(alexa_client):
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
    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    assert call_count + 1 == len(calls)
    call = calls[-1]
    assert call.domain == "test"
    assert call.service == "alexa"
    assert call.data.get("entity_id") == ["switch.test"]
    assert call.data.get("hello") == "virgo"

    data = yield from req.json()
    assert data['response']['card']['title'] == 'Card title for virgo'
    assert data['response']['card']['content'] == 'Card content: virgo'
    assert data['response']['outputSpeech']['type'] == 'PlainText'
    assert data['response']['outputSpeech']['text'] == \
        'Service called for virgo'


@asyncio.coroutine
def test_intent_session_ended_request(alexa_client):
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

    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    text = yield from req.text()
    assert text == ''


@asyncio.coroutine
def test_intent_from_built_in_intent_library(alexa_client):
    """Test intents from the Built-in Intent Library."""
    data = {
        'request': {
            'intent': {
                'name': 'AMAZON.PlaybackAction<object@MusicCreativeWork>',
                'slots': {
                    'object.byArtist.name': {
                        'name': 'object.byArtist.name',
                        'value': 'the shins'
                    },
                    'object.composer.name': {
                        'name': 'object.composer.name'
                    },
                    'object.contentSource': {
                        'name': 'object.contentSource'
                    },
                    'object.era': {
                        'name': 'object.era'
                    },
                    'object.genre': {
                        'name': 'object.genre'
                    },
                    'object.name': {
                        'name': 'object.name'
                    },
                    'object.owner.name': {
                        'name': 'object.owner.name'
                    },
                    'object.select': {
                        'name': 'object.select'
                    },
                    'object.sort': {
                        'name': 'object.sort'
                    },
                    'object.type': {
                        'name': 'object.type',
                        'value': 'music'
                    }
                }
            },
            'timestamp': '2016-12-14T23:23:37Z',
            'type': 'IntentRequest',
            'requestId': REQUEST_ID,

        },
        'session': {
            'sessionId': SESSION_ID,
            'application': {
                'applicationId': APPLICATION_ID
            }
        }
    }
    req = yield from _intent_req(alexa_client, data)
    assert req.status == 200
    data = yield from req.json()
    text = data.get("response", {}).get("outputSpeech",
                                        {}).get("text")
    assert text == "Playing the shins."
