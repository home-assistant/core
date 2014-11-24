"""
test.helper
~~~~~~~~~~~

Helper method for writing tests.
"""


def mock_service(hass, domain, service):
    calls = []

    hass.services.register(
        domain, service, lambda call: calls.append(call))

    return calls
