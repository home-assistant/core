# httpx is aliased to httpx2 at runtime (see homeassistant/__init__.py). Re-export
# httpx2 under the httpx name so dependencies typed against httpx accept httpx2 objects.
from httpx2 import *  # noqa: F403
