from asynciotimers import Timer
import asyncio
from datetime import datetime

async def main():
    delay = 3
    #deltaDelay must be delay >> deltaDelay and deltaDelay >> code runtime
    deltaDelay = 0.2

    loop=asyncio.get_event_loop()
    timerRanOut = loop.create_future()

    def timerCallback():
        if (timerRanOut.done()):
            raise Exception("Timer future already set")
        timerRanOut.set_result(True)
        print("Timer ran out at: ", datetime.now().time())


    testTimer = Timer(delay, timerCallback, loop=loop)
    assert(not testTimer.TimerHandle)

    testTimer.start()
    assert(testTimer.TimerHandle)
    assert(not testTimer._timerDone())
    assert(testTimer._timerActive())
    assert(not timerRanOut.done())

    await asyncio.sleep(delay+deltaDelay)
    assert(testTimer.TimerHandle)
    assert(testTimer._timerDone())
    assert(not testTimer._timerActive())
    assert(timerRanOut.done())

    timerRanOut = loop.create_future()
    testTimer.start()
    testTimer.stop()
    assert(not testTimer._timerActive())
    assert(not timerRanOut.done())

    await asyncio.sleep(delay+deltaDelay)
    assert(not timerRanOut.done())    

    timerRanOut = loop.create_future()
    testTimer.start()
    
    await asyncio.sleep(2*deltaDelay)
    testTimer.reset()

    #Test if the timer is still running
    assert(testTimer.TimerHandle)
    assert(not testTimer._timerDone())
    assert(testTimer._timerActive())
    assert(not timerRanOut.done())

    #Test if the timer is still running when it should have gone off before reset
    await asyncio.sleep(delay-deltaDelay)
    assert(testTimer.TimerHandle)
    assert(not testTimer._timerDone())
    assert(testTimer._timerActive())
    assert(not timerRanOut.done())

    #Test if the timer has gone off after it should have
    await asyncio.sleep(2*deltaDelay)
    assert(testTimer.TimerHandle)
    assert(testTimer._timerDone())
    assert(not testTimer._timerActive())
    assert(timerRanOut.done())

    timerRanOut = loop.create_future()
    await asyncio.sleep(2*delay)
    assert(not timerRanOut.done())


asyncio.run(main())
