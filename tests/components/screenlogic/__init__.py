"""Tests for the Screenlogic integration."""
from collections.abc import Callable
import logging

from tests.common import load_json_object_fixture

MOCK_ADAPTER_NAME = "Pentair DD-EE-FF"
MOCK_ADAPTER_MAC = "aa:bb:cc:dd:ee:ff"
MOCK_ADAPTER_IP = "127.0.0.1"
MOCK_ADAPTER_PORT = 80

_LOGGER = logging.getLogger(__name__)


GATEWAY_DISCOVERY_IMPORT_PATH = "homeassistant.components.screenlogic.coordinator.async_discover_gateways_by_unique_id"


def num_key_string_to_int(data: dict) -> None:
    """Convert all string number dict keys to integer.

    This needed for screenlogicpy's data dict format.
    """
    rpl = []
    for key, value in data.items():
        if isinstance(value, dict):
            num_key_string_to_int(value)
            if isinstance(key, str) and key.isnumeric():
                rpl.append(key)
    for k in rpl:
        data[int(k)] = data.pop(k)

    return data


DATA_FULL_CHEM = num_key_string_to_int(
    load_json_object_fixture("screenlogic/data_full_chem.json")
)
DATA_FULL_NO_GPM = num_key_string_to_int(
    load_json_object_fixture("screenlogic/data_full_no_gpm.json")
)
DATA_FULL_NO_SALT_PPM = num_key_string_to_int(
    load_json_object_fixture("screenlogic/data_full_no_salt_ppm.json")
)
DATA_MIN_MIGRATION = num_key_string_to_int(
    load_json_object_fixture("screenlogic/data_min_migration.json")
)
DATA_MIN_ENTITY_CLEANUP = num_key_string_to_int(
    load_json_object_fixture("screenlogic/data_min_entity_cleanup.json")
)
DATA_MISSING_VALUES_CHEM_CHLOR = num_key_string_to_int(
    load_json_object_fixture("screenlogic/data_missing_values_chem_chlor.json")
)


async def stub_async_connect(
    data,
    self,
    ip=None,
    port=None,
    gtype=None,
    gsubtype=None,
    name=MOCK_ADAPTER_NAME,
    connection_closed_callback: Callable = None,
) -> bool:
    """Initialize minimum attributes needed for tests."""
    self._ip = ip
    self._port = port
    self._type = gtype
    self._subtype = gsubtype
    self._name = name
    self._custom_connection_closed_callback = connection_closed_callback
    self._mac = MOCK_ADAPTER_MAC
    self._data = data
    _LOGGER.debug("Gateway mock connected")

    return True
