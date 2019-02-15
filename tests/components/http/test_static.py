"""Tests for hosting static resource."""
import os
from tempfile import TemporaryDirectory

import pytest

from homeassistant.setup import async_setup_component


async def test_register_static_path(hass, hass_client, aiohttp_client):
    """Test register a dir to host static resources."""
    assert await async_setup_component(hass, 'http', {'http': {}}) is True
    # same hack as the one in http.start()
    # prevent freeze of http app in order to register test path
    hass.http.app._router.freeze = lambda: None
    client = await hass_client()

    with TemporaryDirectory() as tmp_dir:
        # real_path = os.path.realpath(tmp_dir)

        # test default setting is cache-able and no auth need
        default_dir = os.path.join(tmp_dir, 'default')
        os.mkdir(default_dir)

        test_file_path = os.path.join(default_dir, 'test.jpg')
        with open(test_file_path, 'w') as tmp_file:
            tmp_file.write('test')

        hass.http.register_static_path('/default', default_dir)

        # no auth
        resp = await client.get('default/test.jpg',
                                headers={'Authorization': ''})
        assert resp.status == 200
        assert resp.headers['Cache-Control'] == 'public, max-age=2678400'
        assert resp.headers['Content-Type'] == 'image/jpeg'
        assert await resp.text() == 'test'

        # test dynamic content prefer not be cached
        no_cache_dir = os.path.join(tmp_dir, 'no-cache')
        os.mkdir(no_cache_dir)

        test_file_path = os.path.join(no_cache_dir, 'dynamic.mp3')
        with open(test_file_path, 'w') as tmp_file:
            tmp_file.write('no-cache')

        hass.http.register_static_path('/no-cache', no_cache_dir, False)

        resp = await client.get('no-cache/dynamic.mp3')
        assert resp.status == 200
        assert 'Cache-Control' not in resp.headers
        assert resp.headers['Content-Type'] == 'audio/mpeg'
        assert await resp.text() == 'no-cache'

        # test single file register with no cache control
        test_file_path = os.path.join(default_dir, 'dynamic.mp4')
        with open(test_file_path, 'w') as tmp_file:
            tmp_file.write('no-cache')

        hass.http.register_static_path('/nc/d.m', test_file_path, False)

        resp = await client.get('nc/d.m')
        assert resp.status == 200
        assert 'Cache-Control' not in resp.headers
        assert resp.headers['Content-Type'] == 'video/mp4'
        assert await resp.text() == 'no-cache'

        # this file still can be access from cached url
        resp = await client.get('default/dynamic.mp4')
        assert resp.status == 200
        assert resp.headers['Cache-Control'] == 'public, max-age=2678400'
        assert resp.headers['Content-Type'] == 'video/mp4'
        assert await resp.text() == 'no-cache'

        # test single file register with cache control
        test_file_path = os.path.join(no_cache_dir, 'cache.me')
        with open(test_file_path, 'w') as tmp_file:
            tmp_file.write('cached')

        hass.http.register_static_path('/cache.me', test_file_path, True)

        resp = await client.get('cache.me')
        assert resp.status == 200
        assert resp.headers['Cache-Control'] == 'public, max-age=2678400'
        assert resp.headers['Content-Type'] == 'text/troff'
        assert await resp.text() == 'cached'

        # this file still can be access from no-cache url
        resp = await client.get('no-cache/cache.me')
        assert resp.status == 200
        assert 'Cache-Control' not in resp.headers
        assert resp.headers['Content-Type'] == 'text/troff'
        assert await resp.text() == 'cached'

        # test secure feature
        secure_dir = os.path.join(tmp_dir, 'secure')
        os.mkdir(secure_dir)

        test_file_path = os.path.join(secure_dir, 'pass.html')
        with open(test_file_path, 'w') as tmp_file:
            tmp_file.write('<html>pass</html>')

        hass.http.register_static_path('/secure', secure_dir, True,
                                       requires_auth=True)

        resp = await client.get('secure/pass.html')
        assert resp.status == 200
        # secure file is not cache-able, cache-headers parameter is ignored
        assert 'Cache-Control' not in resp.headers
        assert resp.headers['Content-Type'] == 'text/html'
        assert await resp.text() == '<html>pass</html>'

        # negative test: no auth
        resp = await client.get('secure/pass.html',
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
                '/invalid', secure_dir + '/pass.html', False, True)
        with pytest.raises(ValueError):
            hass.http.register_static_path(
                '/invalid', secure_dir + '/not-exist', False, True)



