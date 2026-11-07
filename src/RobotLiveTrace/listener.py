import multiprocessing
import queue
from collections.abc import Callable
from typing import Any

from robot.model import ModelObject  # type: ignore
from robot.utils import safe_str  # type: ignore

from RobotLiveTrace.message import Message


# These only hold IF and TRY branches, so showing them would just add a tree level.
_BRANCH_CONTAINERS = ("IF/ELSE ROOT", "TRY/EXCEPT ROOT")


def _body_item_name(data: Any) -> str:
    if data.type != "ITERATION":
        return str(data)

    # FOR iterations have assigned values, WHILE iterations have none
    values = getattr(data, "assign", {})
    assigned = ", ".join(f"{name} = {safe_str(v)}" for name, v in values.items())
    return f"ITERATION    {assigned}".rstrip()


def _load_run_gui() -> Callable[..., None]:
    """Import the GUI on demand so a broken Dear PyGui install gets a clear error."""
    try:
        from RobotLiveTrace.gui import run_gui
    except ImportError as error:
        raise ImportError(
            f"RobotLiveTrace could not load Dear PyGui: {error}\n"
            "If this mentions GLIBC or GLIBCXX (for example on RHEL, Rocky or "
            "AlmaLinux 9), install a compatible version with: "
            'pip install "dearpygui==2.0.0"'
        ) from error

    return run_gui


class RobotLiveTrace:
    """A Robot Framework listener that provides a real-time execution trace viewer.

    Usage:
        To use this listener, run your Robot Framework tests with the --listener
        option:

        `robot --listener RobotLiveTrace path/to/tests.robot`
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self):
        run_gui = _load_run_gui()

        self.message_queue = multiprocessing.Queue()
        self.pause_event = multiprocessing.Event()
        self.pause_event.set()
        self.pause_on_failure_event = multiprocessing.Event()
        self.last_failure_id = ""

        self.gui_process = multiprocessing.Process(
            target=run_gui,
            args=(self.message_queue, self.pause_event, self.pause_on_failure_event),
        )
        self.gui_process.start()

    def _wait_and_send(
        self,
        action: str,
        data: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ):
        """
        Helper method to enforce pausing and send a message to the GUI.
        """

        if not self.gui_process.is_alive():
            return

        while not self.pause_event.is_set():
            if not self.gui_process.is_alive():
                return
            self.pause_event.wait(timeout=0.2)

        message: Message = {
            "action": action,
            "data": data,
            "result": result,
        }

        try:
            self.message_queue.put(message)
        except (queue.Full, ValueError):
            pass

    def _send_start(self, action: str, data: Any):
        # Only send what the GUI displays. Arguments are converted to strings
        # because libraries can pass any object, including ones that can't be
        # pickled, when calling keywords programmatically.
        payload: dict[str, Any] = {"name": data.name}
        args = getattr(data, "args", ())
        if args:
            payload["args"] = [safe_str(arg) for arg in args]

        self._wait_and_send(action, data=payload)

    def _send_end(self, action: str, result: Any):
        self._wait_and_send(
            action,
            result={
                "status": result.status,
                "elapsed_time": result.elapsed_time.total_seconds(),
            },
        )

    def _pause_if_failure_started_here(self, result: Any):
        """Request a pause, which takes effect when the next event is sent.

        A failure also ends every parent as failed. IDs are hierarchical, so an
        item whose ID prefixes the previous failure's ID is only passing it on.
        """
        if result.status != "FAIL":
            return

        passed_on = self.last_failure_id.startswith(f"{result.id}-")
        self.last_failure_id = result.id

        if not passed_on and self.pause_on_failure_event.is_set():
            self.pause_event.clear()

    def _send_keyword_end(self, action: str, result: Any):
        self._send_end(action, result)
        self._pause_if_failure_started_here(result)

    def start_suite(self, data: ModelObject, result: ModelObject):
        self._send_start("start_suite", data)

    def end_suite(self, data: ModelObject, result: ModelObject):
        self._send_end("end_suite", result)

    def start_test(self, data: ModelObject, result: ModelObject):
        self._send_start("start_test", data)

    def end_test(self, data: ModelObject, result: ModelObject):
        self._send_end("end_test", result)

    def start_user_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._send_start("start_user_keyword", data)

    def end_user_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._send_keyword_end("end_user_keyword", result)

    def start_library_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._send_start("start_library_keyword", data)

    def end_library_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._send_keyword_end("end_library_keyword", result)

    def start_invalid_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._send_start("start_invalid_keyword", data)

    def end_invalid_keyword(
        self,
        data: ModelObject,
        implementation: ModelObject,
        result: ModelObject,
    ):
        self._send_keyword_end("end_invalid_keyword", result)

    def start_body_item(self, data: Any, result: ModelObject):
        """Called for everything without its own method, such as FOR and IF."""
        if data.type not in _BRANCH_CONTAINERS:
            self._wait_and_send(
                f"start_{data.type.lower()}", data={"name": _body_item_name(data)}
            )

    def end_body_item(self, data: Any, result: Any):
        if data.type not in _BRANCH_CONTAINERS:
            self._send_keyword_end(f"end_{data.type.lower()}", result)

    def log_message(self, message: Any):
        result = {"level": message.level, "message": message.message}
        if message.timestamp:
            result["timestamp"] = message.timestamp.isoformat()

        self._wait_and_send("log_message", result=result)

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
