---
title: "Getting the instance URL"
---

In some cases, an integration requires to know the URL of the users' Home
Assistant instance that matches the requirements needed for the use cases at
hand. For example, cause a device needs to communicate back data to Home
Assistant, or for an external service or device to fetch data from Home
Assistant (e.g., a generated image or sound file).

Getting an instance URL can be rather complex, considering a user can have a
bunch of different URLs available:

- A user-configured internal home network URL.
- An automatically detected internal home network URL.
- A user-configured, public accessible, external URL that works from the internet.
- A URL provided by Home Assistant Cloud by Nabu Casa, in case the user has a subscription.

Extra complexity is added by the fact that URLs can be served on non-standard ports
(e.g., not 80 or 443) and with or without SSL (`http://` vs `https://`).

Luckily, Home Assistant provides a helper method to ease that a bit.

## The URL helper

Home Assistant provides a network helper method to get the instance URL,
that matches the requirements the integration needs, called `get_url`.

The signature of the helper method:

```py
# homeassistant.helpers.network.get_url
def get_url(
    hass: HomeAssistant,
    *,
    require_current_request: bool = False,
    require_ssl: bool = False,
    require_standard_port: bool = False,
    allow_internal: bool = True,
    allow_external: bool = True,
    allow_cloud: bool = True,
    allow_ip: bool = True,
    prefer_external: bool = False,
    prefer_cloud: bool = False,
) -> str:
```

The different parameters of the method:

- `require_current_request`
  Require the returned URL to match the URL the user is currently using
  in their browser. If there is no current request, an error will be raised.

- `require_ssl`:
  Require the returned URL to use the `https` scheme.

- `require_standard_port`:
  Require the returned URL use a standard HTTP port. So, it requires port 80
  for the `http` scheme, and port 443 on the `https` scheme.

- `allow_internal`:
  Allow the URL to be an internal set URL by the user or a detected URL on the
  internal network. Set this one to `False` if one requires an external URL
  exclusively.

- `allow_external`:
  Allow the URL to be an external set URL by the user or a Home Assistant Cloud
  URL. Set this one to `False` if one requires an internal URL exclusively.

- `allow_cloud`:
  Allow a Home Assistant Cloud URL to be returned, set to `False` in case one
  requires anything but a Cloud URL.

- `allow_ip`:
  Allow the host part of a URL to be an IP address, set to `False` in case
  that is not usable for the use case.

- `prefer_external`:
  By default, we prefer internal URLs over external ones. Set this option to
  `True` to turn that logic around and prefer an external URL over
  an internal one.

- `prefer_cloud`:
  By default, an external URL set by the user is preferred, however, in rare
  cases a cloud URL might be more reliable. Setting this option to `True`
  prefers the Home Assistant Cloud URL over the user-defined external URL.

## Default behavior

By default, without passing additional parameters (`get_url(hass)`),
it will try to:

- Get an internal URL set by the user, or if not available, try to detect one
  from the network interface (based on `http` settings).

- If an internal URL fails, it will try to get an external URL. It prefers the
  external URL set by the user, in case that fails; Get a Home Assistant Cloud
  URL if that is available.

The default is aimed to be: allow any URL, but prefer a local one,
without requirements.

## Example usage

The most basic example of using the helper:

```py
from homeassistant.helpers.network import get_url

instance_url = get_url(hass)
```

This example call to the helper method would return an internal URL, preferably,
that is either user set or detected. If it cannot provide that, it will try
the users' external URL. Lastly, if that isn't set by the user, it will try to
make use of the Home Assistant Cloud URL.

If absolutely no URL is available (or none match given requirements),
an exception will be raised: `NoURLAvailableError`.

```py
from homeassistant.helpers import network

try:
    external_url = network.get_url(
        hass,
        allow_internal=False,
        allow_ip=False,
        require_ssl=True,
        require_standard_port=True,
    )
except network.NoURLAvailableError:
    raise MyInvalidValueError("Failed to find suitable URL for my integration")
```

The above example shows a little more complex use of the URL helper. In this case
the requested URL may not be an internal address, the URL may not contain an
IP address, requires SSL and must be served on a standard port.

If none is available, the `NoURLAvailableError` exception can be caught and
handled.
