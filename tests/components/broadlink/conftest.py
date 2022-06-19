"""Broadlink test helpers."""
from unittest.mock import patch

import pytest

BROADLINK_CODES = {
    "34ea34befc25": {
        "version": 1,
        "data": {
            "smsl": {
                "standby": "JgBYAAABJpcTEhM4ERMSExE5EhMSFBAVExIQFRA6ExIROhA6EBUQFRE6ExIRFBAVEBURFBEUERQTEhE5EToTOBA5EzkQORE6EwAFkAABKUoTAAxiAAEoSxEADQU=",
                "pwra": "JgBYAAABJpcQFRA6ERQTEhE5ExIRFBIUERQQFRE5FBEROhA6EhMSExE6ExIRFBAVEBUQFREUEBUTEhE5EToRORI4EToRORM4EgAFkQABJ0sRAAxlAAEmTBIADQU=",
                "pwrb": "JgBYAAABJ5YRFBE6EhMQFRA6EhMSExEVEjgSExE5ExITOBE5ERQTExE5ExIRFBITERQRFBEUERUQFRA6EToSOBI5EjgRORI5EwAFawABJk0QAAxlAAEoSxIADQU=",
                "pwrc": "JgBYAAABJpcSExA6EhMRFBE5EhMRFRAVERQRORI5EBUQOhQ2ERQSFBA6ExIRFBEUERQRFBEUERUQFRA6EzcTOBI4EjgROhA6EQAFbQABKEoTAAxiAAEnTBMADQU=",
            },
        },
    }
}


@pytest.fixture(autouse=True)
def mock_heartbeat():
    """Mock broadlink heartbeat."""
    with patch("homeassistant.components.broadlink.heartbeat.blk.ping"):
        yield


@pytest.fixture(autouse=True)
def mock_broadlink_storage(hass_storage):
    """Mock the broadlink stores."""
    for key, value in BROADLINK_CODES.items():
        hass_storage[f"broadlink_remote_{key}_codes"] = value
