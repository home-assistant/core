"""Constants used in Awair tests."""

import json

from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import load_fixture

AWAIR_UUID = "awair_24947"
CONFIG = {CONF_ACCESS_TOKEN: "12345"}
UNIQUE_ID = "foo@bar.com"
DEVICES_FIXTURE = json.loads(load_fixture("awair/devices.json"))
GEN1_DATA_FIXTURE = json.loads(load_fixture("awair/awair.json"))
GEN2_DATA_FIXTURE = json.loads(load_fixture("awair/awair-r2.json"))
GLOW_DATA_FIXTURE = json.loads(load_fixture("awair/glow.json"))
MINT_DATA_FIXTURE = json.loads(load_fixture("awair/mint.json"))
NO_DEVICES_FIXTURE = json.loads(load_fixture("awair/no_devices.json"))
OFFLINE_FIXTURE = json.loads(load_fixture("awair/awair-offline.json"))
OMNI_DATA_FIXTURE = json.loads(load_fixture("awair/omni.json"))
USER_FIXTURE = json.loads(load_fixture("awair/user.json"))
