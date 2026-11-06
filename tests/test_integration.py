"""Run real Robot Framework suites through the listener and replay them in the GUI.

Only the GUI process and Dear PyGui are replaced. Messages are pickled the same way
a multiprocessing queue pickles them, so anything that couldn't reach the real GUI
fails here too.
"""

import io
import itertools
import pickle
import queue
from collections import Counter
from unittest.mock import patch

import pytest
import robot

from RobotLiveTrace.gui import GUI
from RobotLiveTrace.listener import RobotLiveTrace

LIBRARY = """
import threading

from robot.libraries.BuiltIn import BuiltIn


def call_with_objects():
    BuiltIn().run_keyword("Log", 42)
    BuiltIn().run_keyword("Log", threading.Lock())
"""

SUITE = """
*** Settings ***
Library    ObjectArgs.py

*** Test Cases ***
Passing Test
    Greet    world

Non String Arguments
    Call With Objects

Failing Test
    Fail    boom

After The Others
    Log    still running    WARN

*** Keywords ***
Greet
    [Arguments]    ${name}
    Log    Hello ${name}
"""


class PicklingQueue:
    """Stands in for multiprocessing.Queue, including its pickling."""

    def __init__(self):
        self.messages = []

    def put(self, message):
        self.messages.append(pickle.loads(pickle.dumps(message)))

    def cancel_join_thread(self):
        pass


@pytest.fixture(scope="module")
def messages(tmp_path_factory):
    directory = tmp_path_factory.mktemp("suite")
    (directory / "ObjectArgs.py").write_text(LIBRARY)
    suite = directory / "suite.robot"
    suite.write_text(SUITE)

    with patch("RobotLiveTrace.listener.multiprocessing") as mock_multiprocessing:
        message_queue = PicklingQueue()
        mock_multiprocessing.Queue.return_value = message_queue
        mock_multiprocessing.Process.return_value.is_alive.return_value = True
        mock_multiprocessing.Event.return_value.is_set.return_value = True
        listener = RobotLiveTrace()

        return_code = robot.run(
            str(suite),
            listener=listener,
            pythonpath=str(directory),
            output="NONE",
            log="NONE",
            report="NONE",
            console="none",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )

    assert return_code == 1  # Only "Failing Test" fails
    return message_queue.messages


def test_every_start_has_a_matching_end(messages):
    """The GUI pairs starts with ends, so a lost message misplaces later nodes."""
    actions = Counter(message["action"] for message in messages)

    assert actions["start_suite"] == actions["end_suite"] == 1
    assert actions["start_test"] == actions["end_test"] == 4
    assert actions["start_user_keyword"] == actions["end_user_keyword"]
    assert actions["start_library_keyword"] == actions["end_library_keyword"]


def test_all_keyword_arguments_are_strings(messages):
    args = [
        arg
        for message in messages
        if message["action"].startswith("start_")
        for arg in message["data"].get("args", [])
    ]

    assert "42" in args
    assert all(isinstance(arg, str) for arg in args)


def test_end_messages_have_status_and_elapsed_time(messages):
    ends = [message for message in messages if message["action"].startswith("end_")]

    assert {end["result"]["status"] for end in ends} == {"PASS", "FAIL"}
    assert all(isinstance(end["result"]["elapsed_time"], float) for end in ends)


def test_log_messages_have_level_text_and_timestamp(messages):
    logs = [
        message["result"] for message in messages if message["action"] == "log_message"
    ]

    warning = next(log for log in logs if log["message"] == "still running")
    assert warning["level"] == "WARN"
    assert warning["timestamp"]


def test_gui_replays_a_real_run(messages):
    """Every message is handled and the call stack unwinds back to the root."""
    with patch("RobotLiveTrace.gui.dpg") as mock_dpg:
        mock_dpg.add_tree_node.side_effect = itertools.count(1000)
        mock_dpg.does_item_exist.return_value = True
        mock_dpg.get_value.return_value = False

        gui = GUI(queue.Queue())
        gui.themes = dict.fromkeys(
            ["running", "pass", "fail", "log_warn", "log_info"], 1
        )

        for message in messages:
            gui.handle_message(message)

    assert gui.active_stack == ["tree_container"]
    assert any("42" in text for text in gui.node_search_text.values())
