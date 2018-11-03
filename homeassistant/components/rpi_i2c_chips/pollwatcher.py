import logging
import queue
import time
import threading

module_logger = logging.getLogger(__name__)
module_logger.setLevel(logging.DEBUG)


class TimedInputs:
    def __init__(self, inputs, t):
        self.inputs = inputs
        self.time = t

    def __str__(self):
        return "0x%x" % (self.inputs,)


class TimedInputsChange:
    def __init__(self, state, pre_timed_inputs, post_timed_inputs):
        self.state = state
        self.pre_timed_inputs = pre_timed_inputs
        self.post_timed_inputs = post_timed_inputs

    def __str__(self):
        return "<TimedInputsChange: %s -> %s>" % (
            self.pre_timed_inputs,
            self.post_timed_inputs,
        )

    def changed_bits(self):
        """
        Generates (bit_num, current_val) for each changed value
        """
        diffs_mask = (
            self.pre_timed_inputs.inputs ^ self.post_timed_inputs.inputs
        )
        bit_num = 0
        inputs_mask = self.post_timed_inputs.inputs
        while diffs_mask:
            # print ("DEBUG: changed_bits(): diffs_mask: %r" % (diffs_mask, ))
            if diffs_mask & 0x1:
                yield bit_num, inputs_mask & 0x1
            bit_num += 1
            diffs_mask >>= 1
            inputs_mask >>= 1


class ExpanderState:
    """
    Keeps track of previous inputs state of given expander
    Configures exapnder HW, allows read/writes
    Allows to calculate changed bits
    """

    def __init__(self, expander, log=module_logger):
        self.expander = expander
        self.log = log
        self.prev_timed_inputs = None
        self.cur_timed_inputs = None

    def __str__(self):
        return "<%s prev: %s cur: %s>" % (
            self.__class__.__name__,
            self.prev_timed_inputs,
            self.cur_timed_inputs,
        )

    def configure_inputs(self, inputs_mask, set_pull_ups=True, invert=True):
        inputs_mask = self.expander.mask(inputs_mask)
        self.expander.configure_inputs(inputs_mask, pull_ups_mask=inputs_mask)
        self.cur_timed_inputs = self.read_inputs()

    def read_inputs(self):
        inputs = int(self.expander.read_inputs())
        # inputs = inputs & self.input_mask
        # self.log.debug("read_inputs(): masked with input mask(0x%X): 0x%X",
        # self.input_mask, inputs)
        return TimedInputs(inputs, time.time())

    def check_state_changed(self):
        new_timed_inputs = self.read_inputs()
        # self.log.debug("check_state_changed(): self.cur_timed_inputs: %s "
        # "-> new_timed_inputs: %s",
        # self.cur_timed_inputs, new_timed_inputs, )
        if self.prev_timed_inputs is None:
            # First change
            self.prev_timed_inputs = self.cur_timed_inputs
            self.cur_timed_inputs = new_timed_inputs
            # Dummy old state - pretending all inputs changed
            dummy_inputs = self.expander.mask_invert(
                self.cur_timed_inputs.inputs
            )
            dummy_inputs &= self.expander.inputs_mask
            dummy_timed_inputs = TimedInputs(dummy_inputs, time.time())
            ti_change = TimedInputsChange(
                self, dummy_timed_inputs, self.cur_timed_inputs
            )
            return ti_change
        elif new_timed_inputs.inputs != self.cur_timed_inputs.inputs:
            self.prev_timed_inputs = self.cur_timed_inputs
            self.cur_timed_inputs = new_timed_inputs
            ti_change = TimedInputsChange(
                self, self.prev_timed_inputs, self.cur_timed_inputs
            )
            return ti_change
        return None


class CallbackCaller(threading.Thread):
    """
    Thread used to call callbacks, when
    pending exapnder changed states are in queue
    """

    def __init__(self, handler, log=module_logger, name="CallbackCaller"):
        threading.Thread.__init__(self, name=name)
        self.handler = handler
        self.log = log
        self._stop_flag = None  #
        self._run_event = threading.Event()
        self._pending_changed_states_queue = queue.Queue(
            maxsize=100
        )  # TODO: Consider some sane value here ?

    def run(self):
        self.log.info("%s started", self.name)
        while not self._stop_flag:
            # time.sleep(0.1)
            self._run_event.wait(timeout=1.0)
            self._run_event.clear()
            while not self._pending_changed_states_queue.empty():
                changed_states = (
                    self._pending_changed_states_queue.get_nowait()
                )
                try:
                    self.handler(changed_states)
                except Exception as e:
                    self.log.warn("Exception in callback handler: %r/%s", e, e)
        self.log.info("%s finished", self.name)

    def stop(self):
        self._stop_flag = time.time()
        self._run_event.set()

    def add_changes(self, new_changed_states):
        self._pending_changed_states_queue.put_nowait(new_changed_states)
        self.log.debug(
            "New pending_changed_states_queue aprox: len: %d",
            self._pending_changed_states_queue.qsize(),
        )
        self._run_event.set()


class PollWatcher(threading.Thread):
    """
    Thread polling over single I²C bus.
    Adds detected changes to callback caller queue.
    """

    def __init__(self, handler, poll_interval=0.05, log=module_logger):
        threading.Thread.__init__(self, name="PollWatcher")
        self.log = log
        self._stop_event = threading.Event()
        self.poll_interval = poll_interval
        self.expander_states_per_address = {}
        self.callback_caller = CallbackCaller(handler)

    def run(self):
        self.log.info("%s started", self.name)
        try:
            sleep_time = 0
            self.callback_caller.start()
            while not self._stop_event.wait(timeout=sleep_time):
                loop_start_time = time.time()
                changed_states = []
                for state in self.expander_states_per_address.values():
                    # self.log.debug("Processing state: %s" % (state, ))
                    ti_change = None
                    try:
                        ti_change = state.check_state_changed()
                    except OSError as ose:
                        self.log.warn(
                            "Unable to check state of %r: %r/%s",
                            state,
                            ose,
                            ose,
                        )
                        # TODO: Chip dead, bus locked, reset chip/ bus ?
                        continue
                    if ti_change is None:
                        continue
                    changed_states.append(ti_change)
                if changed_states:
                    self.log.debug(
                        "changes detected: %s",
                        " ".join(map(str, changed_states)),
                    )
                    self.callback_caller.add_changes(changed_states)
                sleep_time = self.poll_interval - (
                    time.time() - loop_start_time
                )
                if sleep_time < 0:  # Means polling took longer than interval
                    self.log.warn(
                        "Poll loop took longer (%.3fs) "
                        "than poll interval: %.3fs",
                        self.poll_interval - sleep_time,
                        self.poll_interval,
                    )
                    sleep_time = 0
            # TODO: Join with self.callback_caller() here ?
        finally:
            self.stop()
            self.log.info("%s finished", self.name)

    def stop(self):
        self.callback_caller.stop()
        self._stop_event.set()

    def add_to_watch_expander(self, expander, inputs_mask, log=module_logger):
        state = self.expander_states_per_address.get(expander.address)
        if state is None:
            new_state = ExpanderState(expander, log=log)
            new_state.configure_inputs(inputs_mask)
            self.expander_states_per_address[expander.address] = new_state
        else:  # Already have state
            raise NotImplementedError("TODO: Implement summing up input_masks")


def example_watcher():
    from . import MCP23018

    log = module_logger

    def test_handler(changed_states):
        print("CALLED test_handler(changed_states=%s" % (changed_states,))
        for changed_state in changed_states:
            print(
                "  changed_state: %s :%s"
                % (changed_state.state, changed_state)
            )

    import smbus

    # bus = smbus.SMBus(0)  # Rev 1 Pi uses 0
    bus1 = smbus.SMBus(1)  # Rev 2 Pi uses 1
    mcp23018 = MCP23018.MCP23018(bus1, 0x20)

    pollwatcher = PollWatcher(test_handler, poll_interval=0.05)
    pollwatcher.add_to_watch_expander(mcp23018, 0xC0)

    log.info("Staring PollWatcher")
    pollwatcher.start()

    try:
        input()
    except KeyboardInterrupt:
        log.info("Keyboard interrupt")
        pass
    log.info("Stopping PollWatcher ...")
    pollwatcher.stop()
    log.info("Waiting to join PollWatcher ...")
    pollwatcher.join()
    log.info("Main thread finished")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(relativeCreated)6d %(threadName)s %(message)s",
    )
    example_watcher()
