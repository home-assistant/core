import re
import os
import time
import gzip

from homeassistant.components.http import frontend
import homeassistant.util as util

DOMAIN = 'frontend'
DEPENDENCIES = ['api']

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_MOVED_PERMANENTLY = 301
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_UNPROCESSABLE_ENTITY = 422


URL_ROOT = "/"


def setup(hass, config):
    """ Setup serving the frontend. """
    if 'http' not in hass.components:
        return False

    hass.http.register_path('GET', URL_ROOT, _handle_get_root, False)

    # Static files
    hass.http.register_path(
        'GET', re.compile(r'/static/(?P<file>[a-zA-Z\._\-0-9/]+)'),
        _handle_get_static, False)
    hass.http.register_path(
        'HEAD', re.compile(r'/static/(?P<file>[a-zA-Z\._\-0-9/]+)'),
        _handle_get_static, False)

    return True


def _handle_get_root(handler, path_match, data):
    """ Renders the debug interface. """

    write = lambda txt: handler.wfile.write((txt + "\n").encode("UTF-8"))

    handler.send_response(HTTP_OK)
    handler.send_header('Content-type', 'text/html; charset=utf-8')
    handler.end_headers()

    if handler.server.development:
        app_url = "polymer/splash-login.html"
    else:
        app_url = "frontend-{}.html".format(frontend.VERSION)

    # auto login if no password was set, else check api_password param
    auth = (handler.server.api_password if handler.server.no_password_set
            else data.get('api_password', ''))

    write(("<!doctype html>"
           "<html>"
           "<head><title>Home Assistant</title>"
           "<meta name='mobile-web-app-capable' content='yes'>"
           "<link rel='shortcut icon' href='/static/favicon.ico' />"
           "<link rel='icon' type='image/png' "
           "     href='/static/favicon-192x192.png' sizes='192x192'>"
           "<meta name='viewport' content='width=device-width, "
           "      user-scalable=no, initial-scale=1.0, "
           "      minimum-scale=1.0, maximum-scale=1.0' />"
           "<meta name='theme-color' content='#03a9f4'>"
           "</head>"
           "<body fullbleed>"
           "<h3 id='init' align='center'>Initializing Home Assistant</h3>"
           "<script"
           "     src='/static/webcomponents.min.js'></script>"
           "<link rel='import' href='/static/{}' />"
           "<splash-login auth='{}'></splash-login>"
           "</body></html>").format(app_url, auth))


def _handle_get_static(handler, path_match, data):
    """ Returns a static file. """
    req_file = util.sanitize_path(path_match.group('file'))

    # Strip md5 hash out of frontend filename
    if re.match(r'^frontend-[A-Za-z0-9]{32}\.html$', req_file):
        req_file = "frontend.html"

    path = os.path.join(os.path.dirname(__file__), 'www_static', req_file)

    inp = None

    try:
        inp = open(path, 'rb')

        do_gzip = 'gzip' in handler.headers.get('accept-encoding', '')

        handler.send_response(HTTP_OK)

        ctype = handler.guess_type(path)
        handler.send_header("Content-Type", ctype)

        # Add cache if not development
        if not handler.server.development:
            # 1 year in seconds
            cache_time = 365 * 86400

            handler.send_header(
                "Cache-Control", "public, max-age={}".format(cache_time))
            handler.send_header(
                "Expires", handler.date_time_string(time.time()+cache_time))

        if do_gzip:
            gzip_data = gzip.compress(inp.read())

            handler.send_header("Content-Encoding", "gzip")
            handler.send_header("Vary", "Accept-Encoding")
            handler.send_header("Content-Length", str(len(gzip_data)))

        else:
            fs = os.fstat(inp.fileno())
            handler.send_header("Content-Length", str(fs[6]))

        handler.end_headers()

        if handler.command == 'HEAD':
            return

        elif do_gzip:
            handler.wfile.write(gzip_data)

        else:
            handler.copyfile(inp, handler.wfile)

    except IOError:
        handler.send_response(HTTP_NOT_FOUND)
        handler.end_headers()

    finally:
        if inp:
            inp.close()
