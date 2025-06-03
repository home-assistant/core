"""Test the thread dataset store."""

import asyncio
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from python_otbr_api.tlv_parser import TLVError
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant.components.thread import dataset_store, discovery
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import (
    DATASET_1,
    DATASET_2,
    DATASET_3,
    ROUTER_DISCOVERY_GOOGLE_1,
    ROUTER_DISCOVERY_HASS,
    TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    TEST_BORDER_AGENT_ID,
)

from tests.common import flush_store

# Same as DATASET_1, but PAN ID moved to the end
DATASET_1_REORDERED = (
    "0E080000000000010000000300000F35060004001FFFE0020811111111222222220708FDAD70BF"
    "E5AA15DD051000112233445566778899AABBCCDDEEFF030E4F70656E54687265616444656D6F04"
    "10445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F801021234"
)

DATASET_1_BAD_CHANNEL = (
    "0E080000000000010000000035060004001FFFE0020811111111222222220708FDAD70BF"
    "E5AA15DD051000112233445566778899AABBCCDDEEFF030E4F70656E54687265616444656D6F01"
    "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8"
)

DATASET_1_NO_CHANNEL = (
    "0E08000000000001000035060004001FFFE0020811111111222222250708FDAD70BF"
    "E5AA15DD051000112233445566778899AABBCCDDEEFF030E4F70656E54687265616444656D6F01"
    "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8"
)

DATASET_1_NO_EXTPANID = (
    "0E080000000000010000000300000F35060004001FFFE00708FDAD70BF"
    "E5AA15DD051000112233445566778899AABBCCDDEEFF030E4F70656E54687265616444656D6F01"
    "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8"
)

DATASET_1_NO_ACTIVETIMESTAMP = (
    "000300000F35060004001FFFE0020811111111222222220708FDAD70BF"
    "E5AA15DD051000112233445566778899AABBCCDDEEFF030E4F70656E54687265616444656D6F01"
    "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8"
)

DATASET_1_LARGER_TIMESTAMP = (
    "0E080000000000020000000300000F35060004001FFFE0020811111111222222220708FDAD70BF"
    "E5AA15DD051000112233445566778899AABBCCDDEEFF030E4F70656E54687265616444656D6F01"
    "0212340410445F2B5CA6F2A93A55CE570A70EFEECB0C0402A0F7F8"
)


async def test_add_invalid_dataset(hass: HomeAssistant) -> None:
    """Test adding an invalid dataset."""
    with pytest.raises(TLVError, match="unknown type 222"):
        await dataset_store.async_add_dataset(hass, "source", "DEADBEEF")

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 0


async def test_add_dataset_twice(hass: HomeAssistant) -> None:
    """Test adding dataset twice does nothing."""
    await dataset_store.async_add_dataset(hass, "source", DATASET_1)

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    created = list(store.datasets.values())[0].created

    await dataset_store.async_add_dataset(hass, "new_source", DATASET_1)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].created == created


async def test_add_dataset_reordered(hass: HomeAssistant) -> None:
    """Test adding dataset with keys in a different order does nothing."""
    await dataset_store.async_add_dataset(hass, "source", DATASET_1)

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    created = list(store.datasets.values())[0].created

    await dataset_store.async_add_dataset(hass, "new_source", DATASET_1_REORDERED)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].created == created


async def test_delete_dataset_twice(hass: HomeAssistant) -> None:
    """Test deleting dataset twice raises."""
    await dataset_store.async_add_dataset(hass, "source", DATASET_1)
    await dataset_store.async_add_dataset(hass, "source", DATASET_2)

    store = await dataset_store.async_get_store(hass)
    dataset_id = list(store.datasets.values())[1].id

    store.async_delete(dataset_id)
    assert len(store.datasets) == 1

    with pytest.raises(KeyError, match=f"'{dataset_id}'"):
        store.async_delete(dataset_id)
    assert len(store.datasets) == 1


async def test_delete_preferred_dataset(hass: HomeAssistant) -> None:
    """Test deleting preferred dataset raises."""
    await dataset_store.async_add_dataset(hass, "source", DATASET_1)

    store = await dataset_store.async_get_store(hass)
    dataset_id = list(store.datasets.values())[0].id
    store.preferred_dataset = dataset_id

    with pytest.raises(HomeAssistantError, match="attempt to remove preferred dataset"):
        store.async_delete(dataset_id)
    assert len(store.datasets) == 1


async def test_get_dataset(hass: HomeAssistant) -> None:
    """Test get the preferred dataset."""
    assert await dataset_store.async_get_dataset(hass, "blah") is None

    await dataset_store.async_add_dataset(hass, "source", DATASET_1)
    store = await dataset_store.async_get_store(hass)
    dataset_id = list(store.datasets.values())[0].id

    assert (await dataset_store.async_get_dataset(hass, dataset_id)) == DATASET_1


async def test_get_preferred_dataset(hass: HomeAssistant) -> None:
    """Test get the preferred dataset."""
    assert await dataset_store.async_get_preferred_dataset(hass) is None

    await dataset_store.async_add_dataset(hass, "source", DATASET_1)

    store = await dataset_store.async_get_store(hass)
    dataset_id = list(store.datasets.values())[0].id
    store.preferred_dataset = dataset_id

    assert (await dataset_store.async_get_preferred_dataset(hass)) == DATASET_1


async def test_dataset_properties(hass: HomeAssistant) -> None:
    """Test dataset entry properties."""
    datasets = [
        {"source": "Google", "tlv": DATASET_1},
        {"source": "Multipan", "tlv": DATASET_2},
        {"source": "🎅", "tlv": DATASET_3},
        {"source": "test2", "tlv": DATASET_1_NO_CHANNEL},
    ]

    for dataset in datasets:
        await dataset_store.async_add_dataset(hass, dataset["source"], dataset["tlv"])

    store = await dataset_store.async_get_store(hass)
    for dataset in store.datasets.values():
        if dataset.source == "Google":
            dataset_1 = dataset
        if dataset.source == "Multipan":
            dataset_2 = dataset
        if dataset.source == "🎅":
            dataset_3 = dataset
        if dataset.source == "test2":
            dataset_4 = dataset

    dataset = store.async_get(dataset_1.id)
    assert dataset == dataset_1
    assert dataset.channel == 15
    assert dataset.extended_pan_id == "1111111122222222"
    assert dataset.network_name == "OpenThreadDemo"
    assert dataset.pan_id == "1234"

    dataset = store.async_get(dataset_2.id)
    assert dataset == dataset_2
    assert dataset.channel == 15
    assert dataset.extended_pan_id == "1111111122222233"
    assert dataset.network_name == "HomeAssistant!"
    assert dataset.pan_id == "1234"

    dataset = store.async_get(dataset_3.id)
    assert dataset == dataset_3
    assert dataset.channel == 15
    assert dataset.extended_pan_id == "1111111122222244"
    assert dataset.network_name == "~🐣🐥🐤~"
    assert dataset.pan_id == "1234"

    dataset = store.async_get(dataset_4.id)
    assert dataset == dataset_4
    assert dataset.channel is None


@pytest.mark.parametrize(
    ("dataset", "error"),
    [
        (DATASET_1_BAD_CHANNEL, TLVError),
        (DATASET_1_NO_EXTPANID, HomeAssistantError),
        (DATASET_1_NO_ACTIVETIMESTAMP, HomeAssistantError),
    ],
)
async def test_add_bad_dataset(hass: HomeAssistant, dataset, error) -> None:
    """Test adding a bad dataset."""
    with pytest.raises(error):
        await dataset_store.async_add_dataset(hass, "test", dataset)


async def test_update_dataset_newer(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test updating a dataset."""
    await dataset_store.async_add_dataset(hass, "test", DATASET_1)
    await dataset_store.async_add_dataset(hass, "test", DATASET_1_LARGER_TIMESTAMP)

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_1_LARGER_TIMESTAMP

    assert (
        "Updating dataset with same extended PAN ID and newer active timestamp"
        in caplog.text
    )
    assert (
        "Got dataset with same extended PAN ID and same or older active timestamp"
        not in caplog.text
    )


async def test_update_dataset_older(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test updating a dataset."""
    await dataset_store.async_add_dataset(hass, "test", DATASET_1_LARGER_TIMESTAMP)
    await dataset_store.async_add_dataset(hass, "test", DATASET_1)

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_1_LARGER_TIMESTAMP

    assert (
        "Updating dataset with same extended PAN ID and newer active timestamp"
        not in caplog.text
    )
    assert (
        "Got dataset with same extended PAN ID and same or older active timestamp"
        in caplog.text
    )


async def test_load_datasets(hass: HomeAssistant) -> None:
    """Make sure that we can load/save data correctly."""

    datasets = [
        {
            "source": "Google",
            "tlv": DATASET_1,
        },
        {
            "source": "Multipan",
            "tlv": DATASET_2,
        },
        {
            "source": "🎅",
            "tlv": DATASET_3,
        },
    ]

    store1 = await dataset_store.async_get_store(hass)
    for dataset in datasets:
        store1.async_add(dataset["source"], dataset["tlv"], None, None)
    assert len(store1.datasets) == 3
    dataset_id = list(store1.datasets.values())[0].id
    store1.preferred_dataset = dataset_id

    for dataset in store1.datasets.values():
        if dataset.source == "Google":
            dataset_1_store_1 = dataset
        if dataset.source == "Multipan":
            dataset_2_store_1 = dataset
        if dataset.source == "🎅":
            dataset_3_store_1 = dataset

    assert store1.preferred_dataset == dataset_1_store_1.id

    with pytest.raises(HomeAssistantError):
        store1.async_delete(dataset_1_store_1.id)
    store1.async_delete(dataset_2_store_1.id)

    assert len(store1.datasets) == 2

    store2 = dataset_store.DatasetStore(hass)
    await flush_store(store1._store)
    await store2.async_load()

    assert len(store2.datasets) == 2

    for dataset in store2.datasets.values():
        if dataset.source == "Google":
            dataset_1_store_2 = dataset
        if dataset.source == "🎅":
            dataset_3_store_2 = dataset

    assert list(store1.datasets) == list(store2.datasets)

    assert dataset_1_store_1 == dataset_1_store_2
    assert dataset_3_store_1 == dataset_3_store_2


async def test_loading_datasets_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored datasets on start."""
    hass_storage[dataset_store.STORAGE_KEY] = {
        "version": dataset_store.STORAGE_VERSION_MAJOR,
        "minor_version": dataset_store.STORAGE_VERSION_MINOR,
        "data": {
            "datasets": [
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id1",
                    "preferred_border_agent_id": "230C6A1AC57F6F4BE262ACF32E5EF52C",
                    "preferred_extended_address": "AEEB2F594B570BBF",
                    "source": "source_1",
                    "tlv": DATASET_1,
                },
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id2",
                    "preferred_border_agent_id": None,
                    "preferred_extended_address": "AEEB2F594B570BBF",
                    "source": "source_2",
                    "tlv": DATASET_2,
                },
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id3",
                    "preferred_border_agent_id": None,
                    "preferred_extended_address": None,
                    "source": "source_3",
                    "tlv": DATASET_3,
                },
            ],
            "preferred_dataset": "id1",
        },
    }

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 3
    assert store.preferred_dataset == "id1"


async def test_migrate_drop_bad_datasets(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Test migrating the dataset store when the store has bad datasets."""
    hass_storage[dataset_store.STORAGE_KEY] = {
        "version": dataset_store.STORAGE_VERSION_MAJOR,
        "minor_version": 1,
        "data": {
            "datasets": [
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id1",
                    "source": "source_1",
                    "tlv": DATASET_1,
                },
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id2",
                    "source": "source_2",
                    "tlv": DATASET_1_NO_EXTPANID,
                },
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id3",
                    "source": "source_3",
                    "tlv": DATASET_1_NO_ACTIVETIMESTAMP,
                },
            ],
            "preferred_dataset": "id1",
        },
    }

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_1
    assert store.preferred_dataset == "id1"

    assert f"Dropped invalid Thread dataset '{DATASET_1_NO_EXTPANID}'" in caplog.text
    assert (
        f"Dropped invalid Thread dataset '{DATASET_1_NO_ACTIVETIMESTAMP}'"
        in caplog.text
    )


async def test_migrate_drop_bad_datasets_preferred(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Test migrating the dataset store when the store has bad datasets."""
    hass_storage[dataset_store.STORAGE_KEY] = {
        "version": dataset_store.STORAGE_VERSION_MAJOR,
        "minor_version": 1,
        "data": {
            "datasets": [
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id1",
                    "source": "source_1",
                    "tlv": DATASET_1,
                },
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id2",
                    "source": "source_2",
                    "tlv": DATASET_1_NO_EXTPANID,
                },
            ],
            "preferred_dataset": "id2",
        },
    }

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert store.preferred_dataset is None


async def test_migrate_drop_duplicate_datasets(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Test migrating the dataset store when the store has duplicated datasets."""
    hass_storage[dataset_store.STORAGE_KEY] = {
        "version": dataset_store.STORAGE_VERSION_MAJOR,
        "minor_version": 1,
        "data": {
            "datasets": [
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id1",
                    "source": "source_1",
                    "tlv": DATASET_1,
                },
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id2",
                    "source": "source_2",
                    "tlv": DATASET_1_LARGER_TIMESTAMP,
                },
            ],
            "preferred_dataset": None,
        },
    }

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_1_LARGER_TIMESTAMP
    assert store.preferred_dataset is None

    assert (
        f"Dropped duplicated Thread dataset '{DATASET_1}' "
        f"(duplicate of '{DATASET_1_LARGER_TIMESTAMP}')"
    ) in caplog.text


async def test_migrate_drop_duplicate_datasets_2(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Test migrating the dataset store when the store has duplicated datasets."""
    hass_storage[dataset_store.STORAGE_KEY] = {
        "version": dataset_store.STORAGE_VERSION_MAJOR,
        "minor_version": 1,
        "data": {
            "datasets": [
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id2",
                    "source": "source_2",
                    "tlv": DATASET_1_LARGER_TIMESTAMP,
                },
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id1",
                    "source": "source_1",
                    "tlv": DATASET_1,
                },
            ],
            "preferred_dataset": None,
        },
    }

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_1_LARGER_TIMESTAMP
    assert store.preferred_dataset is None

    assert (
        f"Dropped duplicated Thread dataset '{DATASET_1}' "
        f"(duplicate of '{DATASET_1_LARGER_TIMESTAMP}')"
    ) in caplog.text


async def test_migrate_drop_duplicate_datasets_preferred(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Test migrating the dataset store when the store has duplicated datasets."""
    hass_storage[dataset_store.STORAGE_KEY] = {
        "version": dataset_store.STORAGE_VERSION_MAJOR,
        "minor_version": 1,
        "data": {
            "datasets": [
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id1",
                    "source": "source_1",
                    "tlv": DATASET_1,
                },
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id2",
                    "source": "source_2",
                    "tlv": DATASET_1_LARGER_TIMESTAMP,
                },
            ],
            "preferred_dataset": "id1",
        },
    }

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_1
    assert store.preferred_dataset == "id1"

    assert (
        f"Dropped duplicated Thread dataset '{DATASET_1_LARGER_TIMESTAMP}' "
        f"(duplicate of preferred dataset '{DATASET_1}')"
    ) in caplog.text


async def test_migrate_set_default_border_agent_id(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Test migrating the dataset store adds default border agent."""
    hass_storage[dataset_store.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 2,
        "data": {
            "datasets": [
                {
                    "created": "2023-02-02T09:41:13.746514+00:00",
                    "id": "id1",
                    "source": "source_1",
                    "tlv": DATASET_1,
                },
            ],
            "preferred_dataset": "id1",
        },
    }

    store = await dataset_store.async_get_store(hass)
    assert store.datasets[store._preferred_dataset].preferred_border_agent_id is None
    assert store.datasets[store._preferred_dataset].preferred_extended_address is None


async def test_set_preferred_border_agent_id(hass: HomeAssistant) -> None:
    """Test set the preferred border agent ID of a dataset."""
    assert await dataset_store.async_get_preferred_dataset(hass) is None

    with pytest.raises(HomeAssistantError):
        await dataset_store.async_add_dataset(
            hass, "source", DATASET_3, preferred_border_agent_id="blah"
        )

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 0

    with pytest.raises(HomeAssistantError):
        await dataset_store.async_add_dataset(
            hass, "source", DATASET_3, preferred_border_agent_id="bleh"
        )
    assert len(store.datasets) == 0

    await dataset_store.async_add_dataset(hass, "source", DATASET_2)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].preferred_border_agent_id is None

    with pytest.raises(HomeAssistantError):
        await dataset_store.async_add_dataset(
            hass, "source", DATASET_2, preferred_border_agent_id="blah"
        )
    assert list(store.datasets.values())[0].preferred_border_agent_id is None

    store = await dataset_store.async_get_store(hass)
    dataset_id = list(store.datasets.values())[0].id
    with pytest.raises(HomeAssistantError):
        await store.async_set_preferred_border_agent(dataset_id, "blah", None)
    assert list(store.datasets.values())[0].preferred_border_agent_id is None

    await dataset_store.async_add_dataset(hass, "source", DATASET_1)
    assert len(store.datasets) == 2
    assert list(store.datasets.values())[1].preferred_border_agent_id is None

    with pytest.raises(HomeAssistantError):
        await dataset_store.async_add_dataset(
            hass, "source", DATASET_1_LARGER_TIMESTAMP, preferred_border_agent_id="blah"
        )
    assert list(store.datasets.values())[1].preferred_border_agent_id is None


async def test_set_preferred_border_agent_id_and_extended_address(
    hass: HomeAssistant,
) -> None:
    """Test set the preferred border agent ID and extended address of a dataset."""
    assert await dataset_store.async_get_preferred_dataset(hass) is None

    await dataset_store.async_add_dataset(
        hass,
        "source",
        DATASET_3,
        preferred_border_agent_id="blah",
        preferred_extended_address="bleh",
    )

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].preferred_border_agent_id == "blah"
    assert list(store.datasets.values())[0].preferred_extended_address == "bleh"

    await dataset_store.async_add_dataset(
        hass,
        "source",
        DATASET_3,
        preferred_border_agent_id="bleh",
        preferred_extended_address="bleh",
    )
    assert list(store.datasets.values())[0].preferred_border_agent_id == "blah"
    assert list(store.datasets.values())[0].preferred_extended_address == "bleh"

    await dataset_store.async_add_dataset(hass, "source", DATASET_2)
    assert len(store.datasets) == 2
    assert list(store.datasets.values())[1].preferred_border_agent_id is None
    assert list(store.datasets.values())[1].preferred_extended_address is None

    await dataset_store.async_add_dataset(
        hass,
        "source",
        DATASET_2,
        preferred_border_agent_id="blah",
        preferred_extended_address="bleh",
    )
    assert list(store.datasets.values())[1].preferred_border_agent_id == "blah"
    assert list(store.datasets.values())[1].preferred_extended_address == "bleh"

    await dataset_store.async_add_dataset(hass, "source", DATASET_1)
    assert len(store.datasets) == 3
    assert list(store.datasets.values())[2].preferred_border_agent_id is None
    assert list(store.datasets.values())[2].preferred_extended_address is None

    await dataset_store.async_add_dataset(
        hass,
        "source",
        DATASET_1_LARGER_TIMESTAMP,
        preferred_border_agent_id="blah",
        preferred_extended_address="bleh",
    )
    assert list(store.datasets.values())[2].preferred_border_agent_id == "blah"
    assert list(store.datasets.values())[2].preferred_extended_address == "bleh"


async def test_set_preferred_extended_address(hass: HomeAssistant) -> None:
    """Test set the preferred extended address of a dataset."""
    assert await dataset_store.async_get_preferred_dataset(hass) is None

    await dataset_store.async_add_dataset(
        hass, "source", DATASET_3, preferred_extended_address="blah"
    )

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].preferred_extended_address == "blah"

    await dataset_store.async_add_dataset(
        hass, "source", DATASET_3, preferred_extended_address="bleh"
    )
    assert list(store.datasets.values())[0].preferred_extended_address == "blah"

    await dataset_store.async_add_dataset(hass, "source", DATASET_2)
    assert len(store.datasets) == 2
    assert list(store.datasets.values())[1].preferred_extended_address is None

    await dataset_store.async_add_dataset(
        hass, "source", DATASET_2, preferred_extended_address="blah"
    )
    assert list(store.datasets.values())[1].preferred_extended_address == "blah"

    await dataset_store.async_add_dataset(hass, "source", DATASET_1)
    assert len(store.datasets) == 3
    assert list(store.datasets.values())[2].preferred_extended_address is None

    await dataset_store.async_add_dataset(
        hass, "source", DATASET_1_LARGER_TIMESTAMP, preferred_extended_address="blah"
    )
    assert list(store.datasets.values())[2].preferred_extended_address == "blah"


async def test_automatically_set_preferred_dataset(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test automatically setting the first dataset as the preferred dataset."""
    add_service_listener_called = asyncio.Event()
    remove_service_listener_called = asyncio.Event()

    async def mock_add_service_listener(type_: str, listener: Any):
        add_service_listener_called.set()

    async def mock_remove_service_listener(listener: Any):
        remove_service_listener_called.set()

    mock_async_zeroconf.async_add_service_listener = AsyncMock(
        side_effect=mock_add_service_listener
    )
    mock_async_zeroconf.async_remove_service_listener = AsyncMock(
        side_effect=mock_remove_service_listener
    )
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    with patch(
        "homeassistant.components.thread.dataset_store.BORDER_AGENT_DISCOVERY_TIMEOUT",
        0.1,
    ):
        await dataset_store.async_add_dataset(
            hass,
            "source",
            DATASET_1,
            preferred_border_agent_id=TEST_BORDER_AGENT_ID.hex(),
            preferred_extended_address=TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
        )

        # Wait for discovery to start
        await add_service_listener_called.wait()
        mock_async_zeroconf.async_add_service_listener.assert_called_once_with(
            "_meshcop._udp.local.", ANY
        )

        # Discover a service matching our router
        listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
            mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
        )
        mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
            **ROUTER_DISCOVERY_HASS
        )
        listener.add_service(
            None, ROUTER_DISCOVERY_HASS["type_"], ROUTER_DISCOVERY_HASS["name"]
        )

        # Wait for discovery of other routers to time out and discovery to stop
        await remove_service_listener_called.wait()

    store = await dataset_store.async_get_store(hass)
    assert (
        list(store.datasets.values())[0].preferred_border_agent_id
        == TEST_BORDER_AGENT_ID.hex()
    )
    assert (
        list(store.datasets.values())[0].preferred_extended_address
        == TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex()
    )
    assert await dataset_store.async_get_preferred_dataset(hass) == DATASET_1


async def test_automatically_set_preferred_dataset_own_and_other_router(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test automatically setting the first dataset as the preferred dataset.

    In this test case both our own and another router are found.
    """
    add_service_listener_called = asyncio.Event()
    remove_service_listener_called = asyncio.Event()

    async def mock_add_service_listener(type_: str, listener: Any):
        add_service_listener_called.set()

    async def mock_remove_service_listener(listener: Any):
        remove_service_listener_called.set()

    mock_async_zeroconf.async_add_service_listener = AsyncMock(
        side_effect=mock_add_service_listener
    )
    mock_async_zeroconf.async_remove_service_listener = AsyncMock(
        side_effect=mock_remove_service_listener
    )
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    with patch(
        "homeassistant.components.thread.dataset_store.BORDER_AGENT_DISCOVERY_TIMEOUT",
        0.1,
    ):
        await dataset_store.async_add_dataset(
            hass,
            "source",
            DATASET_1,
            preferred_border_agent_id=TEST_BORDER_AGENT_ID.hex(),
            preferred_extended_address=TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
        )

        # Wait for discovery to start
        await add_service_listener_called.wait()
        mock_async_zeroconf.async_add_service_listener.assert_called_once_with(
            "_meshcop._udp.local.", ANY
        )

        # Discover a service matching our router
        listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
            mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
        )
        mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
            **ROUTER_DISCOVERY_HASS
        )
        listener.add_service(
            None, ROUTER_DISCOVERY_HASS["type_"], ROUTER_DISCOVERY_HASS["name"]
        )

        # Discover another router
        listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
            mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
        )
        mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
            **ROUTER_DISCOVERY_GOOGLE_1
        )
        listener.add_service(
            None, ROUTER_DISCOVERY_GOOGLE_1["type_"], ROUTER_DISCOVERY_GOOGLE_1["name"]
        )

        # Wait for discovery to stop
        await remove_service_listener_called.wait()

    store = await dataset_store.async_get_store(hass)
    assert (
        list(store.datasets.values())[0].preferred_border_agent_id
        == TEST_BORDER_AGENT_ID.hex()
    )
    assert (
        list(store.datasets.values())[0].preferred_extended_address
        == TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex()
    )
    assert await dataset_store.async_get_preferred_dataset(hass) is None


async def test_automatically_set_preferred_dataset_other_router(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test automatically setting the first dataset as the preferred dataset.

    In this test case another router is found.
    """
    add_service_listener_called = asyncio.Event()
    remove_service_listener_called = asyncio.Event()

    async def mock_add_service_listener(type_: str, listener: Any):
        add_service_listener_called.set()

    async def mock_remove_service_listener(listener: Any):
        remove_service_listener_called.set()

    mock_async_zeroconf.async_add_service_listener = AsyncMock(
        side_effect=mock_add_service_listener
    )
    mock_async_zeroconf.async_remove_service_listener = AsyncMock(
        side_effect=mock_remove_service_listener
    )
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    with patch(
        "homeassistant.components.thread.dataset_store.BORDER_AGENT_DISCOVERY_TIMEOUT",
        0.1,
    ):
        await dataset_store.async_add_dataset(
            hass,
            "source",
            DATASET_1,
            preferred_border_agent_id=TEST_BORDER_AGENT_ID.hex(),
            preferred_extended_address=TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
        )

        # Wait for discovery to start
        await add_service_listener_called.wait()
        mock_async_zeroconf.async_add_service_listener.assert_called_once_with(
            "_meshcop._udp.local.", ANY
        )

        # Discover another router
        listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
            mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
        )
        mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
            **ROUTER_DISCOVERY_GOOGLE_1
        )
        listener.add_service(
            None, ROUTER_DISCOVERY_GOOGLE_1["type_"], ROUTER_DISCOVERY_GOOGLE_1["name"]
        )

        # Wait for discovery to stop
        await remove_service_listener_called.wait()

    store = await dataset_store.async_get_store(hass)
    assert (
        list(store.datasets.values())[0].preferred_border_agent_id
        == TEST_BORDER_AGENT_ID.hex()
    )
    assert (
        list(store.datasets.values())[0].preferred_extended_address
        == TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex()
    )
    assert await dataset_store.async_get_preferred_dataset(hass) is None


async def test_automatically_set_preferred_dataset_no_router(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test automatically setting the first dataset as the preferred dataset.

    In this test case no routers are found.
    """
    add_service_listener_called = asyncio.Event()
    remove_service_listener_called = asyncio.Event()

    async def mock_add_service_listener(type_: str, listener: Any):
        add_service_listener_called.set()

    async def mock_remove_service_listener(listener: Any):
        remove_service_listener_called.set()

    mock_async_zeroconf.async_add_service_listener = AsyncMock(
        side_effect=mock_add_service_listener
    )
    mock_async_zeroconf.async_remove_service_listener = AsyncMock(
        side_effect=mock_remove_service_listener
    )
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    with patch(
        "homeassistant.components.thread.dataset_store.BORDER_AGENT_DISCOVERY_TIMEOUT",
        0.1,
    ):
        await dataset_store.async_add_dataset(
            hass,
            "source",
            DATASET_1,
            preferred_border_agent_id=TEST_BORDER_AGENT_ID.hex(),
            preferred_extended_address=TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
        )

        # Wait for discovery to start
        await add_service_listener_called.wait()
        mock_async_zeroconf.async_add_service_listener.assert_called_once_with(
            "_meshcop._udp.local.", ANY
        )

        # Wait for discovery of other routers to time out and discovery to stop
        await remove_service_listener_called.wait()

    store = await dataset_store.async_get_store(hass)
    assert (
        list(store.datasets.values())[0].preferred_border_agent_id
        == TEST_BORDER_AGENT_ID.hex()
    )
    assert (
        list(store.datasets.values())[0].preferred_extended_address
        == TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex()
    )
    assert await dataset_store.async_get_preferred_dataset(hass) is None
