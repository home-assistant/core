"""Constants for the teslemetry tests."""


from homeassistant.const import CONF_ACCESS_TOKEN

COMMAND_SUCCESS = {"response": {"reason": "", "result": True}}
WAKE_AWAKE = {"response": {"state": "online"}}
WAKE_ASLEEP = {"response": {"state": "asleep"}}

CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}
