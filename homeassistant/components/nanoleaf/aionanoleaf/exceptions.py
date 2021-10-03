# Copyright 2021, Milan Meulemans.
#
# This file is part of aionanoleaf.
#
# aionanoleaf is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# aionanoleaf is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with aionanoleaf.  If not, see <https://www.gnu.org/licenses/>.

"""Nanoleaf exceptions."""


class NanoleafException(Exception):
    """General Nanoleaf exception."""


class InvalidEffect(NanoleafException, ValueError):
    """Invalid effect specified."""


class InvalidToken(NanoleafException):
    """Invalid token specified."""


class NoAuthToken(NanoleafException):
    """No auth_token specified."""


class Unauthorized(NanoleafException):
    """Not authorizing new tokens."""


class Unavailable(NanoleafException):
    """Device is unavailable."""
