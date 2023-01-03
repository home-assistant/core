"""Test the Thread integration."""


from homeassistant.components import thread
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker

BASE_URL = "http://core-silabs-multiprotocol:8081"


async def test_get_thread_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_running
):
    """Test async_get_thread_state."""

    aioclient_mock.get(f"{BASE_URL}/node/state", text="0")

    assert await thread.async_get_thread_state(hass) == thread.ThreadState.DISABLED


async def test_set_thread_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_running
):
    """Test async_set_thread_state."""

    aioclient_mock.post(f"{BASE_URL}/node/state", text="0")

    await thread.async_set_thread_state(hass, thread.ThreadState.ROUTER)
    assert 3 == thread.ThreadState.ROUTER.value
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "3"


async def test_get_active_dataset(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_running
):
    """Test async_get_active_dataset."""

    mock_response = {
        "ActiveTimestamp": {
            "Authoritative": False,
            "Seconds": 1,
            "Ticks": 0,
        },
        "ChannelMask": 134215680,
        "Channel": 15,
        "ExtPanId": "8478E3379E047B92",
        "MeshLocalPrefix": "fd89:bde7:42ed:a901::/64",
        "NetworkKey": "96271D6ECC78749114AB6A591E0D06F1",
        "NetworkName": "OpenThread HA",
        "PanId": 33991,
        "PSKc": "9760C89414D461AC717DCD105EB87E5B",
        "SecurityPolicy": {
            "AutonomousEnrollment": False,
            "CommercialCommissioning": False,
            "ExternalCommissioning": True,
            "NativeCommissioning": True,
            "NetworkKeyProvisioning": False,
            "NonCcmRouters": False,
            "ObtainNetworkKey": True,
            "RotationTime": 672,
            "Routers": True,
            "TobleLink": True,
        },
    }

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", json=mock_response)

    active_timestamp = thread.models.Timestamp(
        mock_response["ActiveTimestamp"]["Authoritative"],
        mock_response["ActiveTimestamp"]["Seconds"],
        mock_response["ActiveTimestamp"]["Ticks"],
    )
    security_policy = thread.models.SecurityPolicy(
        mock_response["SecurityPolicy"]["AutonomousEnrollment"],
        mock_response["SecurityPolicy"]["CommercialCommissioning"],
        mock_response["SecurityPolicy"]["ExternalCommissioning"],
        mock_response["SecurityPolicy"]["NativeCommissioning"],
        mock_response["SecurityPolicy"]["NetworkKeyProvisioning"],
        mock_response["SecurityPolicy"]["NonCcmRouters"],
        mock_response["SecurityPolicy"]["ObtainNetworkKey"],
        mock_response["SecurityPolicy"]["RotationTime"],
        mock_response["SecurityPolicy"]["Routers"],
        mock_response["SecurityPolicy"]["TobleLink"],
    )

    assert await thread.async_get_active_dataset(hass) == thread.OperationalDataSet(
        active_timestamp,
        mock_response["ChannelMask"],
        mock_response["Channel"],
        None,  # delay
        mock_response["ExtPanId"],
        mock_response["MeshLocalPrefix"],
        mock_response["NetworkKey"],
        mock_response["NetworkName"],
        mock_response["PanId"],
        None,  # pending_timestamp
        mock_response["PSKc"],
        security_policy,
    )


async def test_get_active_dataset_tlvs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_running
):
    """Test async_get_active_dataset_tlvs."""

    mock_response = (
        "0E080000000000010000000300001035060004001FFFE00208F642646DA209B1C00708FDF57B5A"
        "0FE2AAF60510DE98B5BA1A528FEE049D4B4B01835375030D4F70656E5468726561642048410102"
        "25A40410F5DD18371BFD29E1A601EF6FFAD94C030C0402A0F7F8"
    )

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text=mock_response)

    assert await thread.async_get_active_dataset_tlvs(hass) == bytes.fromhex(
        mock_response
    )


async def test_create_active_dataset(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_running
):
    """Test async_create_active_dataset."""

    aioclient_mock.post(f"{BASE_URL}/node/dataset/active")

    await thread.async_create_active_dataset(hass, thread.OperationalDataSet())
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {}

    await thread.async_create_active_dataset(
        hass, thread.OperationalDataSet(network_name="OpenThread HA")
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {"NetworkName": "OpenThread HA"}

    await thread.async_create_active_dataset(
        hass, thread.OperationalDataSet(network_name="OpenThread HA", channel=15)
    )
    assert aioclient_mock.call_count == 3
    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {
        "NetworkName": "OpenThread HA",
        "Channel": 15,
    }


async def test_set_active_dataset(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_running
):
    """Test async_set_active_dataset."""

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active")

    await thread.async_set_active_dataset(hass, thread.OperationalDataSet())
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {}

    await thread.async_set_active_dataset(
        hass, thread.OperationalDataSet(network_name="OpenThread HA")
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {"NetworkName": "OpenThread HA"}

    await thread.async_set_active_dataset(
        hass, thread.OperationalDataSet(network_name="OpenThread HA", channel=15)
    )
    assert aioclient_mock.call_count == 3
    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {
        "NetworkName": "OpenThread HA",
        "Channel": 15,
    }


async def test_set_active_dataset_tlvs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_running
):
    """Test async_set_active_dataset_tlvs."""

    dataset = bytes.fromhex(
        "0E080000000000010000000300001035060004001FFFE00208F642646DA209B1C00708FDF57B5A"
        "0FE2AAF60510DE98B5BA1A528FEE049D4B4B01835375030D4F70656E5468726561642048410102"
        "25A40410F5DD18371BFD29E1A601EF6FFAD94C030C0402A0F7F8"
    )

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active")

    await thread.async_set_active_dataset_tlvs(hass, dataset)
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == dataset.hex()
    assert aioclient_mock.mock_calls[-1][3] == {"Content-Type": "text/plain"}
