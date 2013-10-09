#Copyright 2013 Paul Barton
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
As the base file, this provides a rough operational model along with the
framework to be extended by each platform.
"""

import time
from threading import Thread

class PyKeyboardMeta(object):
    """
    The base class for PyKeyboard. Represents basic operational model.
    """

    def press_key(self, character=''):
        """Press a given character key."""
        raise NotImplementedError

    def release_key(self, character=''):
        """Release a given character key."""
        raise NotImplementedError

    def tap_key(self, character='', n=1, interval=0):
        """Press and release a given character key n times."""
        for i in xrange(n):
            self.press_key(character)
            self.release_key(character)
            time.sleep(interval)

    def type_string(self, char_string, interval=0):
        """A convenience method for typing longer strings of characters."""
        for i in char_string:
            time.sleep(interval)
            self.tap_key(i)

    def special_key_assignment(self):
        """Makes special keys more accessible."""
        raise NotImplementedError

    def lookup_character_value(self, character):
        """
        If necessary, lookup a valid API value for the key press from the
        character.
        """
        raise NotImplementedError

    def is_char_shifted(self, character):
        """Returns True if the key character is uppercase or shifted."""
        if character.isupper():
            return True
        if character in '<>?:"{}|~!@#$%^&*()_+':
            return True
        return False

class PyKeyboardEventMeta(Thread):
    """
    The base class for PyKeyboard. Represents basic operational model.
    """
    def __init__(self, capture=False):
        Thread.__init__(self)
        self.daemon = True
        self.capture = capture
        self.state = True

    def run(self):
        self.state = True

    def stop(self):
        self.state = False

    def handler(self):
        raise NotImplementedError

    def key_press(self, key):
        """Subclass this method with your key press event handler."""
        pass

    def key_release(self, key):
        """Subclass this method with your key release event handler."""
        pass

    def escape_code(self):
        """
        Defines a means to signal a stop to listening. Subclass this with your
        escape behavior.
        """
        escape = None
        return escape
