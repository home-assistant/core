"""The tests for the hassio component."""
import asyncio

import pytest


@pytest.mark.parametrize(
    'build_type', [
        ("a3_vl", "test/beer/ping?index=1"), ("core", "index.html"),
        ("local", "panel/config"), ("jk_921", "editor.php?idx=3&ping=5")
    ])
async def test_ingress_request_get(
        hassio_client, build_type, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.get(
        "http://127.0.0.1/addons/{}/web/{}".format(build_type[0], build_type[1]),
        text="test"
    )

    resp = await hassio_client.get(
        '/api/hassio_ingress/{}/{}'.format(build_type[0], build_type[1]),
        headers={"x-test-header": "beer"}
    )

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3]["X-HASSIO-KEY"] == "123456"
    assert aioclient_mock.mock_calls[-1][3]["x-test-header"] == "beer"
