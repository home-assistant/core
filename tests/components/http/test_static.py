"""Tests for hosting static resource."""
import os
from tempfile import TemporaryDirectory

import pytest

from homeassistant.setup import async_setup_component


async def test_register_static_path(hass, hass_client, aiohttp_client):
    """Test register a dir to host static resources."""
    assert await async_setup_component(hass, 'http', {'http': {}}) is True
    # use the same hack as the one used in http.start()
    # prevent freeze of http app in order to register static path
    hass.http.app._router.freeze = lambda: None
    client = await hass_client()

    # we are using same test file to save I/O
    with TemporaryDirectory() as tmp_dir:
        # test default setting is cache-able and no auth need
        test_dir = os.path.join(tmp_dir, 'static_test')
        os.mkdir(test_dir)

        test_file_path = os.path.join(test_dir, 'test.jpg')
        with open(test_file_path, 'w') as tmp_file:
            tmp_file.write('test')

        hass.http.register_static_path('/default', test_dir)

        # no auth
        resp = await client.get('default/test.jpg',
                                headers={'Authorization': ''})
        assert resp.status == 200
        assert resp.headers['Cache-Control'] == 'public, max-age=2678400'
        assert resp.headers['Content-Type'] == 'image/jpeg'
        assert await resp.text() == 'test'

        # test dynamic content prefer not be cached
        hass.http.register_static_path('/no-cache', test_dir, False)

        resp = await client.get('no-cache/test.jpg')
        assert resp.status == 200
        assert 'Cache-Control' not in resp.headers
        assert resp.headers['Content-Type'] == 'image/jpeg'
        assert await resp.text() == 'test'

        # test single file register with no cache control
        hass.http.register_static_path('/nc/d.m', test_file_path, False)

        resp = await client.get('nc/d.m')
        assert resp.status == 200
        assert 'Cache-Control' not in resp.headers
        assert resp.headers['Content-Type'] == 'image/jpeg'
        assert await resp.text() == 'test'

        # this file still can be access from cached url
        resp = await client.get('default/test.jpg')
        assert resp.status == 200
        assert resp.headers['Cache-Control'] == 'public, max-age=2678400'
        assert resp.headers['Content-Type'] == 'image/jpeg'
        assert await resp.text() == 'test'

        # test single file register with cache control
        hass.http.register_static_path('/cache.me', test_file_path, True)

        resp = await client.get('cache.me')
        assert resp.status == 200
        assert resp.headers['Cache-Control'] == 'public, max-age=2678400'
        assert resp.headers['Content-Type'] == 'image/jpeg'
        assert await resp.text() == 'test'

        # this file still can be access from no-cache url
        resp = await client.get('no-cache/test.jpg')
        assert resp.status == 200
        assert 'Cache-Control' not in resp.headers
        assert resp.headers['Content-Type'] == 'image/jpeg'
        assert await resp.text() == 'test'

        # test secure feature
        hass.http.register_static_path('/secure', test_dir, True,
                                       requires_auth=True)

        resp = await client.get('secure/test.jpg')
        assert resp.status == 200
        # secure file is not cache-able, cache-headers parameter is ignored
        assert 'Cache-Control' not in resp.headers
        assert resp.headers['Content-Type'] == 'image/jpeg'
        assert await resp.text() == 'test'

        # negative test: no auth
        resp = await client.get('secure/test.jpg',
                                headers={'Authorization': ''})
        assert resp.status == 401
        resp = await client.get('secure/',
                                headers={'Authorization': ''})
        assert resp.status == 401

        # negative test
        resp = await client.get('default/')
        assert resp.status == 403   # not allow list dir
        resp = await client.get('not-valid-path/')
        assert resp.status == 404   # path not found
        resp = await client.get('default/not-valid-file')
        assert resp.status == 404   # file not found

        # negative register test
        with pytest.raises(ValueError):
            hass.http.register_static_path(
                '/invalid', test_dir + '/pass.html', False, True)
        with pytest.raises(ValueError):
            hass.http.register_static_path(
                '/invalid', test_dir + '/not-exist', False, True)
