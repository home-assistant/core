"""Test ONVIF parsers."""

import datetime
import os

import onvif
import onvif.settings
from zeep import Client
from zeep.transports import Transport

from homeassistant.components.onvif import models, parsers
from homeassistant.core import HomeAssistant

TEST_UID = "test-unique-id"


async def get_event(notification_data: dict) -> models.Event:
    """Take in a zeep dict, run it through the parser, and return an Event.

    When the parser encounters an unknown topic that it doesn't know how to parse,
    it outputs a message 'No registered handler for event from ...' along with a
    print out of the serialized xml message from zeep. If it tries to parse and
    can't, it prints out 'Unable to parse event from ...' along with the same
    serialized message. This method can take the output directly from these log
    messages and run them through the parser, which makes it easy to add new unit
    tests that verify the message can now be parsed.
    """
    zeep_client = Client(
        f"{os.path.dirname(onvif.__file__)}/wsdl/events.wsdl",
        wsse=None,
        transport=Transport(),
    )

    notif_msg_type = zeep_client.get_type("ns5:NotificationMessageHolderType")
    assert notif_msg_type is not None
    notif_msg = notif_msg_type(**notification_data)
    assert notif_msg is not None

    # The xsd:any type embedded inside the message doesn't parse, so parse it manually.
    msg_elem = zeep_client.get_element("ns8:Message")
    assert msg_elem is not None
    msg_data = msg_elem(**notification_data["Message"]["_value_1"])
    assert msg_data is not None
    notif_msg.Message._value_1 = msg_data

    parser = parsers.PARSERS.get(notif_msg.Topic._value_1)
    assert parser is not None

    return await parser(TEST_UID, notif_msg)


async def test_line_detector_crossed(hass: HomeAssistant) -> None:
    """Tests tns1:RuleEngine/LineDetector/Crossed."""
    event = await get_event(
        {
            "SubscriptionReference": {
                "Address": {"_value_1": None, "_attr_1": None},
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Topic": {
                "_value_1": "tns1:RuleEngine/LineDetector/Crossed",
                "Dialect": "http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet",
                "_attr_1": {},
            },
            "ProducerReference": {
                "Address": {
                    "_value_1": "xx.xx.xx.xx/onvif/event/alarm",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Message": {
                "_value_1": {
                    "Source": {
                        "SimpleItem": [
                            {
                                "Name": "VideoSourceConfigurationToken",
                                "Value": "video_source_config1",
                            },
                            {
                                "Name": "VideoAnalyticsConfigurationToken",
                                "Value": "analytics_video_source",
                            },
                            {"Name": "Rule", "Value": "MyLineDetectorRule"},
                        ],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Key": None,
                    "Data": {
                        "SimpleItem": [{"Name": "ObjectId", "Value": "0"}],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Extension": None,
                    "UtcTime": datetime.datetime(2020, 5, 24, 7, 24, 47),
                    "PropertyOperation": "Initialized",
                    "_attr_1": {},
                }
            },
        }
    )

    assert event is not None
    assert event.name == "Line Detector Crossed"
    assert event.platform == "sensor"
    assert event.value == "0"
    assert event.uid == (
        f"{TEST_UID}_tns1:RuleEngine/LineDetector/"
        "Crossed_video_source_config1_analytics_video_source_MyLineDetectorRule"
    )


async def test_tapo_line_crossed(hass: HomeAssistant) -> None:
    """Tests tns1:RuleEngine/CellMotionDetector/LineCross."""
    event = await get_event(
        {
            "SubscriptionReference": {
                "Address": {
                    "_value_1": "http://CAMERA_LOCAL_IP:2020/event-0_2020",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Topic": {
                "_value_1": "tns1:RuleEngine/CellMotionDetector/LineCross",
                "Dialect": "http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet",
                "_attr_1": {},
            },
            "ProducerReference": {
                "Address": {
                    "_value_1": "http://CAMERA_LOCAL_IP:5656/event",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Message": {
                "_value_1": {
                    "Source": {
                        "SimpleItem": [
                            {
                                "Name": "VideoSourceConfigurationToken",
                                "Value": "vsconf",
                            },
                            {
                                "Name": "VideoAnalyticsConfigurationToken",
                                "Value": "VideoAnalyticsToken",
                            },
                            {"Name": "Rule", "Value": "MyLineCrossDetectorRule"},
                        ],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Key": None,
                    "Data": {
                        "SimpleItem": [{"Name": "IsLineCross", "Value": "true"}],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Extension": None,
                    "UtcTime": datetime.datetime(
                        2025, 1, 3, 21, 5, 14, tzinfo=datetime.UTC
                    ),
                    "PropertyOperation": "Changed",
                    "_attr_1": {},
                }
            },
        }
    )

    assert event is not None
    assert event.name == "Line Detector Crossed"
    assert event.platform == "binary_sensor"
    assert event.device_class == "motion"
    assert event.value
    assert event.uid == (
        f"{TEST_UID}_tns1:RuleEngine/CellMotionDetector/"
        "LineCross_VideoSourceToken_VideoAnalyticsToken_MyLineCrossDetectorRule"
    )


async def test_tapo_tpsmartevent_vehicle(hass: HomeAssistant) -> None:
    """Tests tns1:RuleEngine/TPSmartEventDetector/TPSmartEvent - vehicle."""
    event = await get_event(
        {
            "Message": {
                "_value_1": {
                    "Data": {
                        "ElementItem": [],
                        "Extension": None,
                        "SimpleItem": [{"Name": "IsVehicle", "Value": "true"}],
                        "_attr_1": None,
                    },
                    "Extension": None,
                    "Key": None,
                    "PropertyOperation": "Changed",
                    "Source": {
                        "ElementItem": [],
                        "Extension": None,
                        "SimpleItem": [
                            {
                                "Name": "VideoSourceConfigurationToken",
                                "Value": "vsconf",
                            },
                            {
                                "Name": "VideoAnalyticsConfigurationToken",
                                "Value": "VideoAnalyticsToken",
                            },
                            {
                                "Name": "Rule",
                                "Value": "MyTPSmartEventDetectorRule",
                            },
                        ],
                        "_attr_1": None,
                    },
                    "UtcTime": datetime.datetime(
                        2024, 11, 2, 0, 33, 11, tzinfo=datetime.UTC
                    ),
                    "_attr_1": {},
                }
            },
            "ProducerReference": {
                "Address": {
                    "_attr_1": None,
                    "_value_1": "http://192.168.56.127:5656/event",
                },
                "Metadata": None,
                "ReferenceParameters": None,
                "_attr_1": None,
                "_value_1": None,
            },
            "SubscriptionReference": {
                "Address": {
                    "_attr_1": None,
                    "_value_1": "http://192.168.56.127:2020/event-0_2020",
                },
                "Metadata": None,
                "ReferenceParameters": None,
                "_attr_1": None,
                "_value_1": None,
            },
            "Topic": {
                "Dialect": "http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet",
                "_attr_1": {},
                "_value_1": "tns1:RuleEngine/TPSmartEventDetector/TPSmartEvent",
            },
        }
    )

    assert event is not None
    assert event.name == "Vehicle Detection"
    assert event.platform == "binary_sensor"
    assert event.device_class == "motion"
    assert event.value
    assert event.uid == (
        f"{TEST_UID}_tns1:RuleEngine/TPSmartEventDetector/"
        "TPSmartEvent_VideoSourceToken_VideoAnalyticsToken_MyTPSmartEventDetectorRule"
    )


async def test_tapo_cellmotiondetector_vehicle(hass: HomeAssistant) -> None:
    """Tests tns1:RuleEngine/CellMotionDetector/TpSmartEvent - vehicle."""
    event = await get_event(
        {
            "SubscriptionReference": {
                "Address": {
                    "_value_1": "http://CAMERA_LOCAL_IP:2020/event-0_2020",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Topic": {
                "_value_1": "tns1:RuleEngine/CellMotionDetector/TpSmartEvent",
                "Dialect": "http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet",
                "_attr_1": {},
            },
            "ProducerReference": {
                "Address": {
                    "_value_1": "http://CAMERA_LOCAL_IP:5656/event",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Message": {
                "_value_1": {
                    "Source": {
                        "SimpleItem": [
                            {
                                "Name": "VideoSourceConfigurationToken",
                                "Value": "vsconf",
                            },
                            {
                                "Name": "VideoAnalyticsConfigurationToken",
                                "Value": "VideoAnalyticsToken",
                            },
                            {"Name": "Rule", "Value": "MyTPSmartEventDetectorRule"},
                        ],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Key": None,
                    "Data": {
                        "SimpleItem": [{"Name": "IsVehicle", "Value": "true"}],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Extension": None,
                    "UtcTime": datetime.datetime(
                        2025, 1, 5, 14, 2, 9, tzinfo=datetime.UTC
                    ),
                    "PropertyOperation": "Changed",
                    "_attr_1": {},
                }
            },
        }
    )

    assert event is not None
    assert event.name == "Vehicle Detection"
    assert event.platform == "binary_sensor"
    assert event.device_class == "motion"
    assert event.value
    assert event.uid == (
        f"{TEST_UID}_tns1:RuleEngine/CellMotionDetector/"
        "TpSmartEvent_VideoSourceToken_VideoAnalyticsToken_MyTPSmartEventDetectorRule"
    )


async def test_tapo_tpsmartevent_person(hass: HomeAssistant) -> None:
    """Tests tns1:RuleEngine/TPSmartEventDetector/TPSmartEvent - person."""
    event = await get_event(
        {
            "Message": {
                "_value_1": {
                    "Data": {
                        "ElementItem": [],
                        "Extension": None,
                        "SimpleItem": [{"Name": "IsPeople", "Value": "true"}],
                        "_attr_1": None,
                    },
                    "Extension": None,
                    "Key": None,
                    "PropertyOperation": "Changed",
                    "Source": {
                        "ElementItem": [],
                        "Extension": None,
                        "SimpleItem": [
                            {
                                "Name": "VideoSourceConfigurationToken",
                                "Value": "vsconf",
                            },
                            {
                                "Name": "VideoAnalyticsConfigurationToken",
                                "Value": "VideoAnalyticsToken",
                            },
                            {"Name": "Rule", "Value": "MyPeopleDetectorRule"},
                        ],
                        "_attr_1": None,
                    },
                    "UtcTime": datetime.datetime(
                        2024, 11, 3, 18, 40, 43, tzinfo=datetime.UTC
                    ),
                    "_attr_1": {},
                }
            },
            "ProducerReference": {
                "Address": {
                    "_attr_1": None,
                    "_value_1": "http://192.168.56.127:5656/event",
                },
                "Metadata": None,
                "ReferenceParameters": None,
                "_attr_1": None,
                "_value_1": None,
            },
            "SubscriptionReference": {
                "Address": {
                    "_attr_1": None,
                    "_value_1": "http://192.168.56.127:2020/event-0_2020",
                },
                "Metadata": None,
                "ReferenceParameters": None,
                "_attr_1": None,
                "_value_1": None,
            },
            "Topic": {
                "Dialect": "http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet",
                "_attr_1": {},
                "_value_1": "tns1:RuleEngine/PeopleDetector/People",
            },
        }
    )

    assert event is not None
    assert event.name == "Person Detection"
    assert event.platform == "binary_sensor"
    assert event.device_class == "motion"
    assert event.value
    assert event.uid == (
        f"{TEST_UID}_tns1:RuleEngine/PeopleDetector/"
        "People_VideoSourceToken_VideoAnalyticsToken_MyPeopleDetectorRule"
    )


async def test_tapo_cellmotiondetector_person(hass: HomeAssistant) -> None:
    """Tests tns1:RuleEngine/CellMotionDetector/People - person."""
    event = await get_event(
        {
            "SubscriptionReference": {
                "Address": {
                    "_value_1": "http://192.168.56.63:2020/event-0_2020",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Topic": {
                "_value_1": "tns1:RuleEngine/CellMotionDetector/People",
                "Dialect": "http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet",
                "_attr_1": {},
            },
            "ProducerReference": {
                "Address": {
                    "_value_1": "http://192.168.56.63:5656/event",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Message": {
                "_value_1": {
                    "Source": {
                        "SimpleItem": [
                            {
                                "Name": "VideoSourceConfigurationToken",
                                "Value": "vsconf",
                            },
                            {
                                "Name": "VideoAnalyticsConfigurationToken",
                                "Value": "VideoAnalyticsToken",
                            },
                            {"Name": "Rule", "Value": "MyPeopleDetectorRule"},
                        ],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Key": None,
                    "Data": {
                        "SimpleItem": [{"Name": "IsPeople", "Value": "true"}],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Extension": None,
                    "UtcTime": datetime.datetime(
                        2025, 1, 3, 20, 9, 22, tzinfo=datetime.UTC
                    ),
                    "PropertyOperation": "Changed",
                    "_attr_1": {},
                }
            },
        }
    )

    assert event is not None
    assert event.name == "Person Detection"
    assert event.platform == "binary_sensor"
    assert event.device_class == "motion"
    assert event.value
    assert event.uid == (
        f"{TEST_UID}_tns1:RuleEngine/CellMotionDetector/"
        "People_VideoSourceToken_VideoAnalyticsToken_MyPeopleDetectorRule"
    )


async def test_tapo_tamper(hass: HomeAssistant) -> None:
    """Tests tns1:RuleEngine/CellMotionDetector/Tamper - tamper."""
    event = await get_event(
        {
            "SubscriptionReference": {
                "Address": {
                    "_value_1": "http://CAMERA_LOCAL_IP:2020/event-0_2020",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Topic": {
                "_value_1": "tns1:RuleEngine/CellMotionDetector/Tamper",
                "Dialect": "http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet",
                "_attr_1": {},
            },
            "ProducerReference": {
                "Address": {
                    "_value_1": "http://CAMERA_LOCAL_IP:5656/event",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Message": {
                "_value_1": {
                    "Source": {
                        "SimpleItem": [
                            {
                                "Name": "VideoSourceConfigurationToken",
                                "Value": "vsconf",
                            },
                            {
                                "Name": "VideoAnalyticsConfigurationToken",
                                "Value": "VideoAnalyticsToken",
                            },
                            {"Name": "Rule", "Value": "MyTamperDetectorRule"},
                        ],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Key": None,
                    "Data": {
                        "SimpleItem": [{"Name": "IsTamper", "Value": "true"}],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Extension": None,
                    "UtcTime": datetime.datetime(
                        2025, 1, 5, 21, 1, 5, tzinfo=datetime.UTC
                    ),
                    "PropertyOperation": "Changed",
                    "_attr_1": {},
                }
            },
        }
    )

    assert event is not None
    assert event.name == "Tamper Detection"
    assert event.platform == "binary_sensor"
    assert event.device_class == "tamper"
    assert event.value
    assert event.uid == (
        f"{TEST_UID}_tns1:RuleEngine/CellMotionDetector/"
        "Tamper_VideoSourceToken_VideoAnalyticsToken_MyTamperDetectorRule"
    )


async def test_tapo_intrusion(hass: HomeAssistant) -> None:
    """Tests tns1:RuleEngine/CellMotionDetector/Intrusion - intrusion."""
    event = await get_event(
        {
            "SubscriptionReference": {
                "Address": {
                    "_value_1": "http://192.168.100.155:2020/event-0_2020",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Topic": {
                "_value_1": "tns1:RuleEngine/CellMotionDetector/Intrusion",
                "Dialect": "http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet",
                "_attr_1": {},
            },
            "ProducerReference": {
                "Address": {
                    "_value_1": "http://192.168.100.155:5656/event",
                    "_attr_1": None,
                },
                "ReferenceParameters": None,
                "Metadata": None,
                "_value_1": None,
                "_attr_1": None,
            },
            "Message": {
                "_value_1": {
                    "Source": {
                        "SimpleItem": [
                            {
                                "Name": "VideoSourceConfigurationToken",
                                "Value": "vsconf",
                            },
                            {
                                "Name": "VideoAnalyticsConfigurationToken",
                                "Value": "VideoAnalyticsToken",
                            },
                            {"Name": "Rule", "Value": "MyIntrusionDetectorRule"},
                        ],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Key": None,
                    "Data": {
                        "SimpleItem": [{"Name": "IsIntrusion", "Value": "true"}],
                        "ElementItem": [],
                        "Extension": None,
                        "_attr_1": None,
                    },
                    "Extension": None,
                    "UtcTime": datetime.datetime(
                        2025, 1, 11, 10, 40, 45, tzinfo=datetime.UTC
                    ),
                    "PropertyOperation": "Changed",
                    "_attr_1": {},
                }
            },
        }
    )

    assert event is not None
    assert event.name == "Intrusion Detection"
    assert event.platform == "binary_sensor"
    assert event.device_class == "safety"
    assert event.value
    assert event.uid == (
        f"{TEST_UID}_tns1:RuleEngine/CellMotionDetector/"
        "Intrusion_VideoSourceToken_VideoAnalyticsToken_MyIntrusionDetectorRule"
    )


async def test_tapo_missing_attributes(hass: HomeAssistant) -> None:
    """Tests async_parse_tplink_detector with missing fields."""
    event = await get_event(
        {
            "Message": {
                "_value_1": {
                    "Data": {
                        "ElementItem": [],
                        "Extension": None,
                        "SimpleItem": [{"Name": "IsPeople", "Value": "true"}],
                        "_attr_1": None,
                    },
                }
            },
            "Topic": {
                "_value_1": "tns1:RuleEngine/PeopleDetector/People",
            },
        }
    )

    assert event is None


async def test_tapo_unknown_type(hass: HomeAssistant) -> None:
    """Tests async_parse_tplink_detector with unknown event type."""
    event = await get_event(
        {
            "Message": {
                "_value_1": {
                    "Data": {
                        "ElementItem": [],
                        "Extension": None,
                        "SimpleItem": [{"Name": "IsNotPerson", "Value": "true"}],
                        "_attr_1": None,
                    },
                    "Source": {
                        "ElementItem": [],
                        "Extension": None,
                        "SimpleItem": [
                            {
                                "Name": "VideoSourceConfigurationToken",
                                "Value": "vsconf",
                            },
                            {
                                "Name": "VideoAnalyticsConfigurationToken",
                                "Value": "VideoAnalyticsToken",
                            },
                            {"Name": "Rule", "Value": "MyPeopleDetectorRule"},
                        ],
                    },
                }
            },
            "Topic": {
                "_value_1": "tns1:RuleEngine/PeopleDetector/People",
            },
        }
    )

    assert event is None
