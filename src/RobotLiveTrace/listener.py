import multiprocessing
import queue

from robot.model import ModelObject  # type: ignore

from RobotLiveTrace.gui import run_gui
from RobotLiveTrace.message import Message


class RobotLiveTrace:
    """A Robot Framework listener that provides a real-time execution trace viewer.

    Usage:
        To use this listener, run your Robot Framework tests with the --listener
        option:

        `robot --listener RobotLiveTrace path/to/tests.robot`
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self):
        self.message_queue = multiprocessing.Queue()
        self.pause_event = multiprocessing.Event()
        self.pause_event.set()

        self.gui_process = multiprocessing.Process(
            target=run_gui, args=(self.message_queue, self.pause_event)
        )
        self.gui_process.start()

    def _wait_and_send(
        self,
        action: str,
        data: ModelObject | None = None,
        result: ModelObject | None = None,
    ):
        """
        Helper method to enforce pausing and serialize data.
        """

        if not self.gui_process.is_alive():
            return

        while not self.pause_event.is_set():
            if not self.gui_process.is_alive():
                return
            self.pause_event.wait(timeout=0.2)

        message: Message = {
            "action": action,
            "data": data.to_dict() if data else None,
            "result": result.to_dict() if result else None,
        }

        try:
            self.message_queue.put(message)
        except (queue.Full, ValueError):
            pass

    def start_suite(self, data: ModelObject, result: ModelObject):
        self._wait_and_send("start_suite", data=data, result=result)

    def end_suite(self, data: ModelObject, result: ModelObject):
        self._wait_and_send("end_suite", data=data, result=result)

    def start_test(self, data: ModelObject, result: ModelObject):
        self._wait_and_send("start_test", data=data, result=result)

    def end_test(self, data: ModelObject, result: ModelObject):
        self._wait_and_send("end_test", data=data, result=result)

    def start_user_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._wait_and_send("start_user_keyword", data=data, result=result)

    def end_user_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._wait_and_send("end_user_keyword", data=data, result=result)

    def start_library_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._wait_and_send("start_library_keyword", data=data, result=result)

    def end_library_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._wait_and_send("end_library_keyword", data=data, result=result)

    def log_message(self, message: ModelObject):
        self._wait_and_send("log_message", result=message)

    def close(self):
        # We join the process here. This intentionally blocks Robot Framework
        # from completely exiting until you manually close the GUI window,
        # allowing you to inspect the final call stack tree.

        self.message_queue.cancel_join_thread()

        if self.gui_process.is_alive():
            print(
                "RobotLiveTrace is open. Close the GUI window to exit Robot Framework."
            )
            self.gui_process.join()
