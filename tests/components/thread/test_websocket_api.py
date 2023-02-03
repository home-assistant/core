"""Test the thread websocket API."""

from homeassistant.components.thread import dataset_store
from homeassistant.components.thread.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import DATASET_1


async def test_add_dataset(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can add a dataset."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 1, "type": "thread/add_dataset_tlv", "source": "test", "tlv": DATASET_1}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    store = await dataset_store._async_get_store(hass)
    assert len(store.datasets) == 1
    dataset = next(iter(store.datasets.values()))
    assert dataset.source == "test"
    assert dataset.tlv == DATASET_1


async def test_add_invalid_dataset(hass: HomeAssistant, hass_ws_client) -> None:
    """Test adding an invalid dataset."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 1, "type": "thread/add_dataset_tlv", "source": "test", "tlv": "DEADBEEF"}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {"code": "invalid_format", "message": "unknown type 222"}
