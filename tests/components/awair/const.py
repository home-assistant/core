"""Constants used in Awair tests."""

import json

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

from tests.common import load_fixture

AWAIR_UUID = "awair_24947"
CLOUD_CONFIG = {CONF_ACCESS_TOKEN: "12345"}
LOCAL_CONFIG = {CONF_HOST: "192.0.2.5"}
CLOUD_UNIQUE_ID = "foo@bar.com"
LOCAL_UNIQUE_ID = "00:B0:D0:63:C2:26"
CLOUD_DEVICES_FIXTURE = json.loads(load_fixture("awair/cloud_devices.json"))
LOCAL_DEVICES_FIXTURE = json.loads(load_fixture("awair/local_devices.json"))
GEN1_DATA_FIXTURE = json.loads(load_fixture("awair/awair.json"))
GEN2_DATA_FIXTURE = json.loads(load_fixture("awair/awair-r2.json"))
GLOW_DATA_FIXTURE = json.loads(load_fixture("awair/glow.json"))
MINT_DATA_FIXTURE = json.loads(load_fixture("awair/mint.json"))
NO_DEVICES_FIXTURE = json.loads(load_fixture("awair/no_devices.json"))
OFFLINE_FIXTURE = json.loads(load_fixture("awair/awair-offline.json"))
OMNI_DATA_FIXTURE = json.loads(load_fixture("awair/omni.json"))
USER_FIXTURE = json.loads(load_fixture("awair/user.json"))
