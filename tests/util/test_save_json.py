"""Test save_json module from JSON Class."""

import json
import orjson
import os.path
from homeassistant.helpers.json import JSONEncoder as DefaultHASSJSONEncoder

import pytest

def save_json(
    filename: str,
    data: dict,
    private: bool = False,
    *,
    encoder: type[json.JSONEncoder],
    atomic_writes: bool = False,
) -> None:
    """Save JSON data to a file.

    Returns True on success.
    """
    dump: Callable[[Any], Any]

    global json_data

    try:
        # For backwards compatibility, if they pass in the
        # default json encoder we use _orjson_default_encoder
        # which is the orjson equivalent to the default encoder.
        if encoder and encoder is not DefaultHASSJSONEncoder:
            # If they pass a custom encoder that is not the
            # DefaultHASSJSONEncoder, we use the slow path of json.dumps
            dump = json.dumps
            json_data = json.dumps(data, indent=2, cls=encoder)
        else:
            dump = orjson.dumps
            json_data = orjson.dumps(data)
    except TypeError as error:
        #msg = f"Failed to serialize to JSON: {filename}. Bad data at {format_unserializable_data(find_paths_unserializable_data(data, dump=dump))}"
        #_LOGGER.error(msg)
        #raise SerializationError(msg) from error
        pass

    if atomic_writes:

        write_utf8_file_atomic(filename, json_data, private)
    else:
        write_utf8_file(filename, json_data, private)

def test_CT1():
    FILENAME = './files/json_ct1.json'
    DATA = {"1": 1}
    PRIVATE = False
    save_json(
        filename=FILENAME,
        data=DATA,
        private=PRIVATE,
        encoder='1',
        atomic_writes = True,
        )
    FILE_EXISTS = os.path.exists('./files/json_ct1.json')
    assert FILE_EXISTS == True

def test_CT2():
    FILENAME = './files/json_ct2.json'
    DATA = {"1": 1}
    PRIVATE = False
    save_json(
        filename=FILENAME,
        data=DATA,
        private=PRIVATE,
        encoder=DefaultHASSJSONEncoder,
        atomic_writes = True,
        )
    FILE_EXISTS = os.path.exists('./files/json_ct2.json')
    assert FILE_EXISTS == True

def test_CT3():
    FILENAME = './files/json_ct3.json'
    DATA = {"1": 1}
    PRIVATE = False
    save_json(
        filename=FILENAME,
        data=DATA,
        private=PRIVATE,
        encoder=None,
        atomic_writes = False,
        )
    FILE_EXISTS = os.path.exists('./files/json_ct3.json')
    assert FILE_EXISTS == True