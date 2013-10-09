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

import time
from Quartz import *
from AppKit import NSEvent
from .base import PyKeyboardMeta, PyKeyboardEventMeta

# Taken from events.h
# /System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/HIToolbox.framework/Versions/A/Headers/Events.h
character_translate_table = {
    'a': 0x00,
    's': 0x01,
    'd': 0x02,
    'f': 0x03,
    'h': 0x04,
    'g': 0x05,
    'z': 0x06,
    'x': 0x07,
    'c': 0x08,
    'v': 0x09,
    'b': 0x0b,
    'q': 0x0c,
    'w': 0x0d,
    'e': 0x0e,
    'r': 0x0f,
    'y': 0x10,
    't': 0x11,
    '1': 0x12,
    '2': 0x13,
    '3': 0x14,
    '4': 0x15,
    '6': 0x16,
    '5': 0x17,
    '=': 0x18,
    '9': 0x19,
    '7': 0x1a,
    '-': 0x1b,
    '8': 0x1c,
    '0': 0x1d,
    ']': 0x1e,
    'o': 0x1f,
    'u': 0x20,
    '[': 0x21,
    'i': 0x22,
    'p': 0x23,
    'l': 0x25,
    'j': 0x26,
    '\'': 0x27,
    'k': 0x28,
    ';': 0x29,
    '\\': 0x2a,
    ',': 0x2b,
    '/': 0x2c,
    'n': 0x2d,
    'm': 0x2e,
    '.': 0x2f,
    '`': 0x32,
    ' ': 0x31,
    '\r': 0x24,
    '\t': 0x30,
    'shift': 0x38
}

# Taken from ev_keymap.h
# http://www.opensource.apple.com/source/IOHIDFamily/IOHIDFamily-86.1/IOHIDSystem/IOKit/hidsystem/ev_keymap.h
special_key_translate_table = {
    'KEYTYPE_SOUND_UP': 0,
    'KEYTYPE_SOUND_DOWN': 1,
    'KEYTYPE_BRIGHTNESS_UP': 2,
    'KEYTYPE_BRIGHTNESS_DOWN': 3,
    'KEYTYPE_CAPS_LOCK': 4,
    'KEYTYPE_HELP': 5,
    'POWER_KEY': 6,
    'KEYTYPE_MUTE': 7,
    'UP_ARROW_KEY': 8,
    'DOWN_ARROW_KEY': 9,
    'KEYTYPE_NUM_LOCK': 10,
    'KEYTYPE_CONTRAST_UP': 11,
    'KEYTYPE_CONTRAST_DOWN': 12,
    'KEYTYPE_LAUNCH_PANEL': 13,
    'KEYTYPE_EJECT': 14,
    'KEYTYPE_VIDMIRROR': 15,
    'KEYTYPE_PLAY': 16,
    'KEYTYPE_NEXT': 17,
    'KEYTYPE_PREVIOUS': 18,
    'KEYTYPE_FAST': 19,
    'KEYTYPE_REWIND': 20,
    'KEYTYPE_ILLUMINATION_UP': 21,
    'KEYTYPE_ILLUMINATION_DOWN': 22,
    'KEYTYPE_ILLUMINATION_TOGGLE': 23
}

class PyKeyboard(PyKeyboardMeta):
    def press_key(self, key):
        if key in special_key_translate_table:
            self._press_special_key(key, True)
        else:
            self._press_normal_key(key, True)

    def release_key(self, key):
        if key in special_key_translate_table:
            self._press_special_key(key, False)
        else:
            self._press_normal_key(key, False)

    def special_key_assignment(self):
        self.volume_mute_key = 'KEYTYPE_MUTE'
        self.volume_down_key = 'KEYTYPE_SOUND_DOWN'
        self.volume_up_key = 'KEYTYPE_SOUND_UP'
        self.media_play_pause_key = 'KEYTYPE_PLAY'

        # Doesn't work :(
        # self.media_next_track_key = 'KEYTYPE_NEXT'
        # self.media_prev_track_key = 'KEYTYPE_PREVIOUS'

    def _press_normal_key(self, key, down):
        try:
            if self.is_char_shifted(key):
                key_code = character_translate_table[key.lower()]

                event = CGEventCreateKeyboardEvent(None, 
                            character_translate_table['shift'], down)
                CGEventPost(kCGHIDEventTap, event)
                # Tiny sleep to let OS X catch up on us pressing shift
                time.sleep(.01)

            else:
                key_code = character_translate_table[key]


            event = CGEventCreateKeyboardEvent(None, key_code, down)
            CGEventPost(kCGHIDEventTap, event)


        except KeyError:
            raise RuntimeError("Key {} not implemented.".format(key))

    def _press_special_key(self, key, down):
        """ Helper method for special keys. 

        Source: http://stackoverflow.com/questions/11045814/emulate-media-key-press-on-mac
        """
        key_code = special_key_translate_table[key]

        ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                NSSystemDefined, # type
                (0,0), # location
                0xa00 if down else 0xb00, # flags
                0, # timestamp
                0, # window
                0, # ctx
                8, # subtype
                (key_code << 16) | ((0xa if down else 0xb) << 8), # data1
                -1 # data2
            )

        CGEventPost(0, ev.CGEvent())

class PyKeyboardEvent(PyKeyboardEventMeta):
    def run(self):
        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            CGEventMaskBit(kCGEventKeyDown) |
            CGEventMaskBit(kCGEventKeyUp),
            self.handler,
            None)

        loopsource = CFMachPortCreateRunLoopSource(None, tap, 0)
        loop = CFRunLoopGetCurrent()
        CFRunLoopAddSource(loop, loopsource, kCFRunLoopDefaultMode)
        CGEventTapEnable(tap, True)

        while self.state:
            CFRunLoopRunInMode(kCFRunLoopDefaultMode, 5, False)

    def handler(self, proxy, type, event, refcon):
        key = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
        if type == kCGEventKeyDown:
            self.key_press(key)
        elif type == kCGEventKeyUp:
            self.key_release(key)

        if self.capture:
            CGEventSetType(event, kCGEventNull)

        return event
