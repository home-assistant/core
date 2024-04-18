"""The tests for the person component."""

import logging

import pytest

from homeassistant.components import person
from homeassistant.components.person import DOMAIN
from homeassistant.helpers import collection
from homeassistant.setup import async_setup_component

DEVICE_TRACKER = "device_tracker.test_tracker"
DEVICE_TRACKER_2 = "device_tracker.test_tracker_2"


@pytest.fixture
def storage_collection(hass):
    """Return an empty storage collection."""
    id_manager = collection.IDManager()
    return person.PersonStorageCollection(
        person.PersonStore(hass, person.STORAGE_VERSION, person.STORAGE_KEY),
        id_manager,
        collection.YamlCollection(
            logging.getLogger(f"{person.__name__}.yaml_collection"), id_manager
        ),
    )


@pytest.fixture
def storage_setup(hass, hass_storage, hass_admin_user):
    """Storage setup."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {
            "persons": [
                {
                    "id": "1234",
                    "name": "tracked person",
                    "user_id": hass_admin_user.id,
                    "device_trackers": [DEVICE_TRACKER],
                }
            ]
        },
    }
    assert hass.loop.run_until_complete(async_setup_component(hass, DOMAIN, {}))
