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

from Xlib.display import Display
from Xlib import X
from Xlib.ext.xtest import fake_input
from Xlib.XK import string_to_keysym, keysym_to_string
from Xlib.ext import record
from Xlib.protocol import rq

from .base import PyKeyboardMeta, PyKeyboardEventMeta

import time

special_X_keysyms = {
    ' ': "space",
    '\t': "Tab",
    '\n': "Return",  # for some reason this needs to be cr, not lf
    '\r': "Return",
    '\e': "Escape",
    '!': "exclam",
    '#': "numbersign",
    '%': "percent",
    '$': "dollar",
    '&': "ampersand",
    '"': "quotedbl",
    '\'': "apostrophe",
    '(': "parenleft",
    ')': "parenright",
    '*': "asterisk",
    '=': "equal",
    '+': "plus",
    ',': "comma",
    '-': "minus",
    '.': "period",
    '/': "slash",
    ':': "colon",
    ';': "semicolon",
    '<': "less",
    '>': "greater",
    '?': "question",
    '@': "at",
    '[': "bracketleft",
    ']': "bracketright",
    '\\': "backslash",
    '^': "asciicircum",
    '_': "underscore",
    '`': "grave",
    '{': "braceleft",
    '|': "bar",
    '}': "braceright",
    '~': "asciitilde"
    }

class PyKeyboard(PyKeyboardMeta):
    """
    The PyKeyboard implementation for X11 systems (mostly linux). This
    allows one to simulate keyboard input.
    """
    def __init__(self, display=None):
        PyKeyboardMeta.__init__(self)
        self.display = Display(display)
        self.display2 = Display(display)
        self.special_key_assignment()

    def press_key(self, character=''):
        """
        Press a given character key. Also works with character keycodes as
        integers, but not keysyms.
        """
        try:  # Detect uppercase or shifted character
            shifted = self.is_char_shifted(character)
        except AttributeError:  # Handle the case of integer keycode argument
            fake_input(self.display, X.KeyPress, character)
            self.display.sync()
        else:
            if shifted:
                fake_input(self.display, X.KeyPress, self.shift_key)
            char_val = self.lookup_character_value(character)
            fake_input(self.display, X.KeyPress, char_val)
            self.display.sync()

    def release_key(self, character=''):
        """
        Release a given character key. Also works with character keycodes as
        integers, but not keysyms.
        """
        try:  # Detect uppercase or shifted character
            shifted = self.is_char_shifted(character)
        except AttributeError:  # Handle the case of integer keycode argument
            fake_input(self.display, X.KeyRelease, character)
            self.display.sync()
        else:
            if shifted:
                fake_input(self.display, X.KeyRelease, self.shift_key)
            char_val = self.lookup_character_value(character)
            fake_input(self.display, X.KeyRelease, char_val)
            self.display.sync()

    def special_key_assignment(self):
        """
        Determines the keycodes for common special keys on the keyboard. These
        are integer values and can be passed to the other key methods.
        Generally speaking, these are non-printable codes.
        """
        #This set of keys compiled using the X11 keysymdef.h file as reference
        #They comprise a relatively universal set of keys, though there may be
        #exceptions which may come up for other OSes and vendors. Countless
        #special cases exist which are not handled here, but may be extended.
        #TTY Function Keys
        self.backspace_key = self.lookup_character_value('BackSpace')
        self.tab_key = self.lookup_character_value('Tab')
        self.linefeed_key = self.lookup_character_value('Linefeed')
        self.clear_key = self.lookup_character_value('Clear')
        self.return_key = self.lookup_character_value('Return')
        self.enter_key = self.return_key  # Because many keyboards call it "Enter"
        self.pause_key = self.lookup_character_value('Pause')
        self.scroll_lock_key = self.lookup_character_value('Scroll_Lock')
        self.sys_req_key = self.lookup_character_value('Sys_Req')
        self.escape_key = self.lookup_character_value('Escape')
        self.delete_key = self.lookup_character_value('Delete')
        #Modifier Keys
        self.shift_l_key = self.lookup_character_value('Shift_L')
        self.shift_r_key = self.lookup_character_value('Shift_R')
        self.shift_key = self.shift_l_key  # Default Shift is left Shift
        self.alt_l_key = self.lookup_character_value('Alt_L')
        self.alt_r_key = self.lookup_character_value('Alt_R')
        self.alt_key = self.alt_l_key  # Default Alt is left Alt
        self.control_l_key = self.lookup_character_value('Control_L')
        self.control_r_key = self.lookup_character_value('Control_R')
        self.control_key = self.control_l_key  # Default Ctrl is left Ctrl
        self.caps_lock_key = self.lookup_character_value('Caps_Lock')
        self.capital_key = self.caps_lock_key  # Some may know it as Capital
        self.shift_lock_key = self.lookup_character_value('Shift_Lock')
        self.meta_l_key = self.lookup_character_value('Meta_L')
        self.meta_r_key = self.lookup_character_value('Meta_R')
        self.super_l_key = self.lookup_character_value('Super_L')
        self.windows_l_key = self.super_l_key  # Cross-support; also it's printed there
        self.super_r_key = self.lookup_character_value('Super_R')
        self.windows_r_key = self.super_r_key  # Cross-support; also it's printed there
        self.hyper_l_key = self.lookup_character_value('Hyper_L')
        self.hyper_r_key = self.lookup_character_value('Hyper_R')
        #Cursor Control and Motion
        self.home_key = self.lookup_character_value('Home')
        self.up_key = self.lookup_character_value('Up')
        self.down_key = self.lookup_character_value('Down')
        self.left_key = self.lookup_character_value('Left')
        self.right_key = self.lookup_character_value('Right')
        self.end_key = self.lookup_character_value('End')
        self.begin_key = self.lookup_character_value('Begin')
        self.page_up_key = self.lookup_character_value('Page_Up')
        self.page_down_key = self.lookup_character_value('Page_Down')
        self.prior_key = self.lookup_character_value('Prior')
        self.next_key = self.lookup_character_value('Next')
        #Misc Functions
        self.select_key = self.lookup_character_value('Select')
        self.print_key = self.lookup_character_value('Print')
        self.print_screen_key = self.print_key  # Seems to be the same thing
        self.snapshot_key = self.print_key  # Another name for printscreen
        self.execute_key = self.lookup_character_value('Execute')
        self.insert_key = self.lookup_character_value('Insert')
        self.undo_key = self.lookup_character_value('Undo')
        self.redo_key = self.lookup_character_value('Redo')
        self.menu_key = self.lookup_character_value('Menu')
        self.apps_key = self.menu_key  # Windows...
        self.find_key = self.lookup_character_value('Find')
        self.cancel_key = self.lookup_character_value('Cancel')
        self.help_key = self.lookup_character_value('Help')
        self.break_key = self.lookup_character_value('Break')
        self.mode_switch_key = self.lookup_character_value('Mode_switch')
        self.script_switch_key = self.lookup_character_value('script_switch')
        self.num_lock_key = self.lookup_character_value('Num_Lock')
        #Keypad Keys: Dictionary structure
        keypad = ['Space', 'Tab', 'Enter', 'F1', 'F2', 'F3', 'F4', 'Home',
                  'Left', 'Up', 'Right', 'Down', 'Prior', 'Page_Up', 'Next',
                  'Page_Down', 'End', 'Begin', 'Insert', 'Delete', 'Equal',
                  'Multiply', 'Add', 'Separator', 'Subtract', 'Decimal',
                  'Divide', 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        self.keypad_keys = {k: self.lookup_character_value('KP_'+str(k)) for k in keypad}
        self.numpad_keys = self.keypad_keys
        #Function Keys/ Auxilliary Keys
        #FKeys
        self.function_keys = [None] + [self.lookup_character_value('F'+str(i)) for i in xrange(1,36)]
        #LKeys
        self.l_keys = [None] + [self.lookup_character_value('L'+str(i)) for i in xrange(1,11)]
        #RKeys
        self.r_keys = [None] + [self.lookup_character_value('R'+str(i)) for i in xrange(1,16)]

        #Unsupported keys from windows
        self.kana_key = None
        self.hangeul_key = None # old name - should be here for compatibility
        self.hangul_key = None
        self.junjua_key = None
        self.final_key = None
        self.hanja_key = None
        self.kanji_key = None
        self.convert_key = None
        self.nonconvert_key = None
        self.accept_key = None
        self.modechange_key = None
        self.sleep_key = None

    def lookup_character_value(self, character):
        """
        Looks up the keysym for the character then returns the keycode mapping
        for that keysym.
        """
        ch_keysym = string_to_keysym(character)
        if ch_keysym == 0:
            ch_keysym = string_to_keysym(special_X_keysyms[character])
        return self.display.keysym_to_keycode(ch_keysym)

class PyKeyboardEvent(PyKeyboardEventMeta):
    """
    The PyKeyboardEvent implementation for X11 systems (mostly linux). This
    allows one to listen for keyboard input.
    """
    def __init__(self, display=None):
        PyKeyboardEventMeta.__init__(self)
        self.display = Display(display)
        self.display2 = Display(display)
        self.ctx = self.display2.record_create_context(
            0,
            [record.AllClients],
            [{
                    'core_requests': (0, 0),
                    'core_replies': (0, 0),
                    'ext_requests': (0, 0, 0, 0),
                    'ext_replies': (0, 0, 0, 0),
                    'delivered_events': (0, 0),
                    'device_events': (X.KeyPress, X.KeyRelease),
                    'errors': (0, 0),
                    'client_started': False,
                    'client_died': False,
            }])
        self.shift_state = 0  # 0 is off, 1 is on
        self.alt_state = 0  # 0 is off, 2 is on
        self.mod_keycodes = self.get_mod_keycodes()

    def run(self):
        """Begin listening for keyboard input events."""
        self.state = True
        if self.capture:
            self.display2.screen().root.grab_keyboard(True, X.KeyPressMask | X.KeyReleaseMask, X.GrabModeAsync, X.GrabModeAsync, 0, 0, X.CurrentTime)

        self.display2.record_enable_context(self.ctx, self.handler)
        self.display2.record_free_context(self.ctx)

    def stop(self):
        """Stop listening for keyboard input events."""
        self.state = False
        self.display.record_disable_context(self.ctx)
        self.display.ungrab_keyboard(X.CurrentTime)
        self.display.flush()
        self.display2.record_disable_context(self.ctx)
        self.display2.ungrab_keyboard(X.CurrentTime)
        self.display2.flush()

    def handler(self, reply):
        """Upper level handler of keyboard events."""
        data = reply.data
        while len(data):
            event, data = rq.EventField(None).parse_binary_value(data, self.display.display, None, None)
            if event.type == X.KeyPress:
                if self.escape_code(event):  # Quit if this returns True
                    self.stop()
                else:
                    self._key_press(event.detail)
            elif event.type == X.KeyRelease:
                self._key_release(event.detail)
            else:
                print('WTF: {0}'.format(event.type))

    def _key_press(self, keycode):
        """A key has been pressed, do stuff."""
        #Alter modification states
        if keycode in self.mod_keycodes['Shift'] or keycode in self.mod_keycodes['Lock']:
            self.toggle_shift_state()
        elif keycode in self.mod_keycodes['Alt']:
            self.toggle_alt_state()
        else:
            self.key_press(keycode)

    def _key_release(self, keycode):
        """A key has been released, do stuff."""
        #Alter modification states
        if keycode in self.mod_keycodes['Shift']:
            self.toggle_shift_state()
        elif keycode in self.mod_keycodes['Alt']:
            self.toggle_alt_state()
        else:
            self.key_release(keycode)

    def escape_code(self, event):
        if event.detail == self.lookup_character_value('Escape'):
            return True
        return False

    def lookup_char_from_keycode(self, keycode):
        keysym =self.display.keycode_to_keysym(keycode, self.shift_state + self.alt_state)
        if keysym:
            char = self.display.lookup_string(keysym)
            return char
        else:
            return None

    def get_mod_keycodes(self):
        """
        Detects keycodes for modifiers and parses them into a dictionary
        for easy access.
        """
        modifier_mapping = self.display.get_modifier_mapping()
        modifier_dict = {}
        nti = [('Shift', X.ShiftMapIndex),
               ('Control', X.ControlMapIndex), ('Mod1', X.Mod1MapIndex),
               ('Alt', X.Mod1MapIndex), ('Mod2', X.Mod2MapIndex),
               ('Mod3', X.Mod3MapIndex), ('Mod4', X.Mod4MapIndex),
               ('Mod5', X.Mod5MapIndex), ('Lock', X.LockMapIndex)]
        for n, i in nti:
            modifier_dict[n] = list(modifier_mapping[i])
        return modifier_dict

    def lookup_character_value(self, character):
        """
        Looks up the keysym for the character then returns the keycode mapping
        for that keysym.
        """
        ch_keysym = string_to_keysym(character)
        if ch_keysym == 0:
            ch_keysym = string_to_keysym(special_X_keysyms[character])
        return self.display.keysym_to_keycode(ch_keysym)

    def toggle_shift_state(self):
        '''Does toggling for the shift state.'''
        if self.shift_state == 0:
            self.shift_state = 1
        elif self.shift_state == 1:
            self.shift_state = 0
        else:
            return False
        return True

    def toggle_alt_state(self):
        '''Does toggling for the alt state.'''
        if self.alt_state == 0:
            self.alt_state = 2
        elif self.alt_state == 2:
            self.alt_state = 0
        else:
            return False
        return True
