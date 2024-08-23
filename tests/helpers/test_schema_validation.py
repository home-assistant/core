"""The tests for helper config validation."""

from homeassistant.helpers.config_validation import TRIGGER_SCHEMA


async def test_nested_trigger_list() -> None:
    """Test triggers within nested lists are flattened."""

    automation = {
        "automation": {
            "trigger": [
                {
                    "triggers": {
                        "platform": "event",
                        "event_type": "trigger_1",
                    },
                },
                {
                    "platform": "event",
                    "event_type": "trigger_2",
                },
                {"triggers": []},
                {"triggers": None},
                {
                    "triggers": [
                        {
                            "platform": "event",
                            "event_type": "trigger_3",
                        },
                        {
                            "platform": "event",
                            "event_type": "trigger_4",
                        },
                    ],
                },
            ],
            "action": {
                "service": "test.automation",
            },
        }
    }

    validatedTriggers = TRIGGER_SCHEMA(automation["automation"]["trigger"])

    assert len(validatedTriggers) == 4
    assert validatedTriggers[0]["event_type"] == "trigger_1"
    assert validatedTriggers[1]["event_type"] == "trigger_2"
    assert validatedTriggers[2]["event_type"] == "trigger_3"
    assert validatedTriggers[3]["event_type"] == "trigger_4"
