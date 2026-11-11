"""Constants for the Bbox integration."""

DEFAULT_HOST = "mabbox.bytel.fr"

# Wait of the sync→async bridge: the legacy platforms run in executor
# threads. The worst fetch chains three client requests (request, login,
# retry), each with the 10 s client timeout of the API client, plus
# session overhead.
REQUEST_TIMEOUT = 35  # seconds
