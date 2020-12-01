import asyncio
import warnings

class Timer(object):
#async Timer object with start, stop reset and garbage collection using futures and and loop.call_later
    def __init__(self, delay, callback, *args, loop=None):
        self.TimerHandle = None
        self.setTimeout(delay)
        self.setCallback(callback)
        self.callback = callback
        self.args = args
        if loop:
            self.loop = loop
        else:
            self.loop = asyncio.get_event_loop()

    def setTimeout(self, delay):
        if self._timerActive():
            warnings.warn("A timer was still running with the old delay. delay won't be changed untill next reset()")
        self.delay = delay
    
    def setCallback(self, callback):
        if callable(callback):
            if self._timerActive():
                warnings.warn("A timer was still running with the old callback. callback won't be changed untill next reset()")
            self.callback = callback
        else:
            raise Exception("callback for Timer is not callable")


    def start(self):
        if not self._timerActive():
            self.TimerHandle = self.loop.call_later(self.delay, self.callback, *self.args)
        else:
            raise Exception("Timer already started")

    def stop(self):
        if not self.TimerHandle:
            raise Exception("Timer was stopped before being started")
        elif self.TimerHandle.cancelled():
            warnings.warn("Timer was stopped, before being stopped again")
        elif self._timerDone():
            warnings.warn("Timer was finished, before being stopped")
        self.TimerHandle.cancel()

    def reset(self):
        if not self.TimerHandle:
            warnings.warn("Timer was not started while being reset")
        elif not self._timerDone():
            self.stop()
        self.TimerHandle = None
        self.start()

    def done(self):
        return self._timerActive()

    def _timerDone(self):
        if self.TimerHandle:
            return ((self.loop.time() - self.TimerHandle.when()) >= 0)
        else:
            return False

    def _timerActive(self):
        return (self.TimerHandle and not self.TimerHandle.cancelled() and not self._timerDone())

    def __del__(self):
        if self._timerActive():
            self.TimerHandle.cancel()
