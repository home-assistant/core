"""Test the Open Thread Border Router integration."""

from http import HTTPStatus

import pytest

from homeassistant.components import otbr
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.test_util.aiohttp import AiohttpClientMocker

BASE_URL = "http://core-silabs-multiprotocol:8081"


async def test_remove_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_thread_state."""

    aioclient_mock.get(f"{BASE_URL}/node/state", text="0")

    assert await otbr.async_get_thread_state(hass) == otbr.ThreadState.DISABLED

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    await hass.config_entries.async_remove(config_entry.entry_id)

    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_thread_state(hass)


async def test_get_thread_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_thread_state."""

    aioclient_mock.get(f"{BASE_URL}/node/state", text="0")

    assert await otbr.async_get_thread_state(hass) == otbr.ThreadState.DISABLED


async def test_set_thread_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_thread_state."""

    aioclient_mock.post(f"{BASE_URL}/node/state", text="0")

    await otbr.async_set_thread_state(hass, otbr.ThreadState.ROUTER)
    assert 3 == otbr.ThreadState.ROUTER.value
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "3"


async def test_get_active_dataset(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
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

    active_timestamp = otbr.models.Timestamp(
        mock_response["ActiveTimestamp"]["Authoritative"],
        mock_response["ActiveTimestamp"]["Seconds"],
        mock_response["ActiveTimestamp"]["Ticks"],
    )
    security_policy = otbr.models.SecurityPolicy(
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

    active_dataset = await otbr.async_get_active_dataset(hass)
    assert active_dataset == otbr.OperationalDataSet(
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
    assert active_dataset.as_json() == mock_response


async def test_get_active_dataset_empty(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_active_dataset."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    assert await otbr.async_get_active_dataset(hass) is None


async def test_get_active_dataset_tlvs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_active_dataset_tlvs."""

    mock_response = (
        "0E080000000000010000000300001035060004001FFFE00208F642646DA209B1C00708FDF57B5A"
        "0FE2AAF60510DE98B5BA1A528FEE049D4B4B01835375030D4F70656E5468726561642048410102"
        "25A40410F5DD18371BFD29E1A601EF6FFAD94C030C0402A0F7F8"
    )

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text=mock_response)

    assert await otbr.async_get_active_dataset_tlvs(hass) == bytes.fromhex(
        mock_response
    )


async def test_get_active_dataset_tlvs_empty(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_active_dataset_tlvs."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    assert await otbr.async_get_active_dataset_tlvs(hass) is None


async def test_create_active_dataset(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_create_active_dataset."""

    aioclient_mock.post(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.ACCEPTED)

    await otbr.async_create_active_dataset(hass, otbr.OperationalDataSet())
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {}

    await otbr.async_create_active_dataset(
        hass, otbr.OperationalDataSet(network_name="OpenThread HA")
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {"NetworkName": "OpenThread HA"}

    await otbr.async_create_active_dataset(
        hass, otbr.OperationalDataSet(network_name="OpenThread HA", channel=15)
    )
    assert aioclient_mock.call_count == 3
    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {
        "NetworkName": "OpenThread HA",
        "Channel": 15,
    }


async def test_create_active_dataset_thread_active(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_create_active_dataset."""

    aioclient_mock.post(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.CONFLICT)

    with pytest.raises(otbr.ThreadNetworkActiveError):
        await otbr.async_create_active_dataset(hass, otbr.OperationalDataSet())


async def test_set_active_dataset(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_active_dataset."""

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.ACCEPTED)

    await otbr.async_set_active_dataset(hass, otbr.OperationalDataSet())
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {}

    await otbr.async_set_active_dataset(
        hass, otbr.OperationalDataSet(network_name="OpenThread HA")
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {"NetworkName": "OpenThread HA"}

    await otbr.async_set_active_dataset(
        hass, otbr.OperationalDataSet(network_name="OpenThread HA", channel=15)
    )
    assert aioclient_mock.call_count == 3
    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == {
        "NetworkName": "OpenThread HA",
        "Channel": 15,
    }


async def test_set_active_dataset_no_dataset(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_active_dataset."""

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.NOT_FOUND)

    with pytest.raises(otbr.NoDatasetError):
        await otbr.async_set_active_dataset(hass, otbr.OperationalDataSet())


async def test_set_active_dataset_thread_active(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_active_dataset."""

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.CONFLICT)

    with pytest.raises(otbr.ThreadNetworkActiveError):
        await otbr.async_set_active_dataset(hass, otbr.OperationalDataSet())


async def test_set_active_dataset_tlvs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_active_dataset_tlvs."""

    dataset = bytes.fromhex(
        "0E080000000000010000000300001035060004001FFFE00208F642646DA209B1C00708FDF57B5A"
        "0FE2AAF60510DE98B5BA1A528FEE049D4B4B01835375030D4F70656E5468726561642048410102"
        "25A40410F5DD18371BFD29E1A601EF6FFAD94C030C0402A0F7F8"
    )

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.ACCEPTED)

    await otbr.async_set_active_dataset_tlvs(hass, dataset)
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-1][2] == dataset.hex()
    assert aioclient_mock.mock_calls[-1][3] == {"Content-Type": "text/plain"}


async def test_set_active_dataset_tlvs_no_dataset(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_active_dataset_tlvs."""

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.NOT_FOUND)

    with pytest.raises(otbr.NoDatasetError):
        await otbr.async_set_active_dataset_tlvs(hass, b"")


async def test_set_active_dataset_tlvs_thread_active(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_active_dataset_tlvs."""

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.CONFLICT)

    with pytest.raises(otbr.ThreadNetworkActiveError):
        await otbr.async_set_active_dataset_tlvs(hass, b"")


async def test_get_thread_state_addon_not_installed(hass: HomeAssistant):
    """Test async_get_thread_state when the multi-PAN addon is not installed."""

    with pytest.raises(HomeAssistantError):
        await otbr.async_get_thread_state(hass)


async def test_get_thread_state_404(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_thread_state with error."""

    aioclient_mock.get(f"{BASE_URL}/node/state", status=HTTPStatus.NOT_FOUND)
    with pytest.raises(HomeAssistantError):
        await otbr.async_get_thread_state(hass)


async def test_get_thread_state_204(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_thread_state with error."""

    aioclient_mock.get(f"{BASE_URL}/node/state", status=HTTPStatus.NO_CONTENT)
    with pytest.raises(HomeAssistantError):
        await otbr.async_get_thread_state(hass)


async def test_get_thread_state_invalid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_thread_state with error."""

    aioclient_mock.get(f"{BASE_URL}/node/state", text="unexpected")
    with pytest.raises(HomeAssistantError):
        await otbr.async_get_thread_state(hass)


async def test_set_thread_state_204(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_thread_state with error."""

    aioclient_mock.post(f"{BASE_URL}/node/state", status=HTTPStatus.NO_CONTENT)
    with pytest.raises(HomeAssistantError):
        await otbr.async_set_thread_state(hass, otbr.ThreadState.ROUTER)


async def test_get_active_dataset_201(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_active_dataset with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.CREATED)
    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset(hass) is None


async def test_get_active_dataset_invalid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_active_dataset with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text="unexpected")
    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset(hass) is None


async def test_get_active_dataset_tlvs_201(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_active_dataset_tlvs with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.CREATED)
    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset_tlvs(hass) is None


async def test_get_active_dataset_tlvs_invalid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_get_active_dataset_tlvs with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text="unexpected")
    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset_tlvs(hass) is None


async def test_create_active_dataset_thread_active_200(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_create_active_dataset with error."""

    aioclient_mock.post(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.OK)

    with pytest.raises(HomeAssistantError):
        await otbr.async_create_active_dataset(hass, otbr.OperationalDataSet())


async def test_set_active_dataset_thread_active_200(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_active_dataset with error."""

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.OK)

    with pytest.raises(HomeAssistantError):
        await otbr.async_set_active_dataset(hass, otbr.OperationalDataSet())


async def test_set_active_dataset_tlvs_thread_active_200(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, thread_config_entry
):
    """Test async_set_active_dataset with error."""

    aioclient_mock.put(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.OK)

    with pytest.raises(HomeAssistantError):
        await otbr.async_set_active_dataset_tlvs(hass, b"")
