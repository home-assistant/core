"""Constants used for testing the bangolufsen integration."""

from multiprocessing.pool import AsyncResult, Pool
from unittest.mock import Mock

from mozart_api.exceptions import ApiException
from mozart_api.models import BeolinkPeer, VolumeLevel, VolumeSettings
from urllib3.exceptions import MaxRetryError, NewConnectionError

from homeassistant.components.bangolufsen.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_ITEM_NUMBER,
    ATTR_SERIAL_NUMBER,
    ATTR_TYPE_NUMBER,
    CONF_BEOLINK_JID,
    CONF_DEFAULT_VOLUME,
    CONF_MAX_VOLUME,
    CONF_VOLUME_STEP,
)
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME


class TestConstants:
    """Constants for general testing."""

    TEST_HOST = "192.168.0.1"
    TEST_HOST_INVALID = "192.168.0"
    TEST_MODEL_BALANCE = "Beosound Balance"
    TEST_MODEL_THEATRE = "Beosound Theatre"
    TEST_MODEL_LEVEL = "Beosound Level"
    TEST_SERIAL_NUMBER = "11111111"
    TEST_NAME = f"{TEST_MODEL_BALANCE}-{TEST_SERIAL_NUMBER}"
    TEST_FRIENDLY_NAME = "Living room Balance"
    TEST_TYPE_NUMBER = "1111"
    TEST_ITEM_NUMBER = "1111111"
    TEST_JID_1 = f"{TEST_TYPE_NUMBER}.{TEST_ITEM_NUMBER}.{TEST_SERIAL_NUMBER}@products.bang-olufsen.com"
    TEST_JID_2 = f"{2222}.{2222222}.{22222222}@products.bang-olufsen.com"
    TEST_JID_3 = f"{3333}.{3333333}.{33333333}@products.bang-olufsen.com"
    TEST_DEFAULT_VOLUME = 40
    TEST_MAX_VOLUME = 100
    TEST_VOLUME_STEP = 5


class TestConstantsConfigFlow(TestConstants):
    """Constants for test_config_flow."""

    SETUP_ENTRY = "homeassistant.components.bangolufsen.async_setup_entry"

    TEST_HOST_OPTIONS = "192.168.0.2"
    TEST_NAME_OPTIONS = "Test name options"
    TEST_DEFAULT_VOLUME_OPTIONS = 20
    TEST_MAX_VOLUME_OPTIONS = 70
    TEST_VOLUME_STEP_OPTIONS = 7

    TEST_HOSTNAME_ZEROCONF = TestConstants.TEST_NAME.replace(" ", "-") + ".local."
    TEST_TYPE_ZEROCONF = "_bangolufsen._tcp.local."
    TEST_NAME_ZEROCONF = (
        TestConstants.TEST_NAME.replace(" ", "-") + "." + TEST_TYPE_ZEROCONF
    )

    TEST_DATA_ONLY_HOST = {CONF_HOST: TestConstants.TEST_HOST}
    TEST_DATA_ONLY_HOST_INVALID = {CONF_HOST: TestConstants.TEST_HOST_INVALID}

    TEST_DATA_NO_HOST = {
        CONF_VOLUME_STEP: TestConstants.TEST_VOLUME_STEP,
        CONF_DEFAULT_VOLUME: TestConstants.TEST_DEFAULT_VOLUME,
        CONF_MAX_VOLUME: TestConstants.TEST_MAX_VOLUME,
    }

    TEST_DATA_FULL = {
        CONF_HOST: TestConstants.TEST_HOST,
        CONF_NAME: TestConstants.TEST_NAME,
        CONF_VOLUME_STEP: TestConstants.TEST_VOLUME_STEP,
        CONF_DEFAULT_VOLUME: TestConstants.TEST_DEFAULT_VOLUME,
        CONF_MAX_VOLUME: TestConstants.TEST_MAX_VOLUME,
        CONF_MODEL: TestConstants.TEST_MODEL_BALANCE,
        CONF_BEOLINK_JID: TestConstants.TEST_JID_1,
    }

    TEST_DATA_ZEROCONF = ZeroconfServiceInfo(
        addresses=[TestConstants.TEST_HOST],
        host=TestConstants.TEST_HOST,
        port=80,
        hostname=TEST_HOSTNAME_ZEROCONF,
        type=TEST_TYPE_ZEROCONF,
        name=TEST_NAME_ZEROCONF,
        properties={
            ATTR_FRIENDLY_NAME: TestConstants.TEST_FRIENDLY_NAME,
            ATTR_SERIAL_NUMBER: TestConstants.TEST_SERIAL_NUMBER,
            ATTR_TYPE_NUMBER: TestConstants.TEST_TYPE_NUMBER,
            ATTR_ITEM_NUMBER: TestConstants.TEST_ITEM_NUMBER,
        },
    )

    TEST_DATA_ZEROCONF_NOT_MOZART = ZeroconfServiceInfo(
        addresses=[TestConstants.TEST_HOST],
        host=TestConstants.TEST_HOST,
        port=80,
        hostname=TEST_HOSTNAME_ZEROCONF,
        type=TEST_TYPE_ZEROCONF,
        name=TEST_NAME_ZEROCONF,
        properties={ATTR_SERIAL_NUMBER: TestConstants.TEST_SERIAL_NUMBER},
    )

    TEST_DATA_OPTIONS = {
        CONF_NAME: TEST_NAME_OPTIONS,
        CONF_VOLUME_STEP: TEST_VOLUME_STEP_OPTIONS,
        CONF_DEFAULT_VOLUME: TEST_DEFAULT_VOLUME_OPTIONS,
        CONF_MAX_VOLUME: TEST_MAX_VOLUME_OPTIONS,
    }
    TEST_DATA_OPTIONS_FULL = {
        CONF_HOST: TestConstants.TEST_HOST,
        CONF_NAME: TEST_NAME_OPTIONS,
        CONF_VOLUME_STEP: TEST_VOLUME_STEP_OPTIONS,
        CONF_DEFAULT_VOLUME: TEST_DEFAULT_VOLUME_OPTIONS,
        CONF_MAX_VOLUME: TEST_MAX_VOLUME_OPTIONS,
        CONF_MODEL: TestConstants.TEST_MODEL_BALANCE,
        CONF_BEOLINK_JID: TestConstants.TEST_JID_1,
    }


class MockMozartClient:
    """Class for mocking MozartClient objects and methods."""

    class Methods:
        """Class for mocking methods directly instead of the client object."""

        get_result = "multiprocessing.pool.ApplyResult.get"

        get_beolink_self = "mozart_api.mozart_client.MozartClient.get_beolink_self"
        get_volume_settings = (
            "mozart_api.mozart_client.MozartClient.get_volume_settings"
        )

        def __init__(self) -> None:
            """Initialize Methods."""
            self.pool = Pool()

        def __del__(self) -> None:
            """Teardown."""
            self.pool.close()
            self.pool.join()

        def async_result(self) -> AsyncResult:
            """Get method result."""
            return self.pool.apply_async(func=None)

    class Get:
        """Class for storing the results from method calls."""

        get_beolink_self = BeolinkPeer(
            friendly_name=TestConstants.TEST_FRIENDLY_NAME, jid=TestConstants.TEST_JID_1
        )

        get_volume_settings = VolumeSettings(
            default=VolumeLevel(level=TestConstants.TEST_DEFAULT_VOLUME),
            maximum=VolumeLevel(level=TestConstants.TEST_MAX_VOLUME),
        )

    __test__ = False

    api_exception = ApiException()
    new_connection_error = NewConnectionError(pool=None, message=None)
    max_retry_error = MaxRetryError(pool=None, url=None)
    value_error = ValueError()

    # REST API methods
    def get_beolink_self(self, **kwargs):
        """Mock get_beolink_self call."""
        self._get_beolink_self(**kwargs)
        return self._get_beolink_self

    def get_volume_settings(self, **kwargs):
        """Mock get_volume_settings call."""
        self._get_volume_settings(**kwargs)
        return self._get_volume_settings

    def __init__(self) -> None:
        """Initialize MockMozartClient."""
        self.get = self.Get()
        self.methods = self.Methods()

        # REST API methods
        self._get_beolink_self = Mock()
        self._get_beolink_self.get = Mock(return_value=self.get.get_beolink_self)

        self._get_volume_settings = Mock()
        self._get_volume_settings.get = Mock(return_value=self.get.get_volume_settings)
