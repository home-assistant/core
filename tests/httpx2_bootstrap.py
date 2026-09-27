"""Install HTTPX2 aliases before pytest plugins import HTTPX."""

from httpx2 import alias_httpx

alias_httpx()
