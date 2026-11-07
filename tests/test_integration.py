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

Control Structures
    FOR    ${i}    IN RANGE    2
        IF    ${i} == 1
            Log    one
        ELSE
            Log    other
        END
    END
    ${n} =    Set Variable    ${0}
    WHILE    ${n} < 1
        ${n} =    Evaluate    ${n} + 1
    END

Missing Keyword
    This Keyword Does Not Exist
    Log    never runs

Skipped Test
    Skip    not today

Handled Failure
    TRY
        Fail    expected
    EXCEPT    expected
        Log    handled
    FINALLY
        Log    cleaned up
    END

Nested Failure
    Fails Inside
    Log    never runs
    [Teardown]    Log    tearing down

*** Keywords ***
Greet
    [Arguments]    ${name}
    Log    Hello ${name}

Fails Inside
    Fail    deep
    [Teardown]    Log    keyword teardown
"""

# "Failing Test", "Missing Keyword" and "Nested Failure" fail
FAILED_TESTS = 3
TEST_COUNT = 9


class RunningEvent:
    """A set multiprocessing.Event that counts requests to pause but never blocks."""

    def __init__(self):
        self.clear_count = 0

    def set(self):
        pass

    def is_set(self):
        return True

    def wait(self, timeout=None):
        return True

    def clear(self):
        self.clear_count += 1


class PicklingQueue:
    """Stands in for multiprocessing.Queue, including its pickling."""

    def __init__(self):
        self.messages = []

    def put(self, message):
        self.messages.append(pickle.loads(pickle.dumps(message)))

    def cancel_join_thread(self):
        pass


@pytest.fixture(scope="module")
def listener(tmp_path_factory):
    directory = tmp_path_factory.mktemp("suite")
    (directory / "ObjectArgs.py").write_text(LIBRARY)
    suite = directory / "suite.robot"
    suite.write_text(SUITE)

    with patch("RobotLiveTrace.listener.multiprocessing") as mock_multiprocessing:
        message_queue = PicklingQueue()
        mock_multiprocessing.Queue.return_value = message_queue
        mock_multiprocessing.Process.return_value.is_alive.return_value = True
        mock_multiprocessing.Event.side_effect = RunningEvent
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

    assert return_code == FAILED_TESTS
    return listener


@pytest.fixture(scope="module")
def messages(listener):
    return listener.message_queue.messages


def actions_named(messages, *names):
    return [m["data"]["name"] for m in messages if m["action"] in names]


def test_every_start_has_a_matching_end(messages):
    """The GUI pairs starts with ends, so a lost message misplaces later nodes."""
    actions = Counter(message["action"] for message in messages)

    assert actions["start_suite"] == actions["end_suite"] == 1
    assert actions["start_test"] == actions["end_test"] == TEST_COUNT

    starts = {a.removeprefix("start_") for a in actions if a.startswith("start_")}
    assert {"for", "iteration", "if", "else", "while"} <= starts
    for name in starts:
        assert actions[f"start_{name}"] == actions[f"end_{name}"], name


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

    statuses = {end["result"]["status"] for end in ends}
    assert statuses == {"PASS", "FAIL", "SKIP", "NOT RUN"}
    assert all(isinstance(end["result"]["elapsed_time"], float) for end in ends)


def test_log_messages_have_level_text_and_timestamp(messages):
    logs = [
        message["result"] for message in messages if message["action"] == "log_message"
    ]

    warning = next(log for log in logs if log["message"] == "still running")
    assert warning["level"] == "WARN"
    assert warning["timestamp"]


def test_control_structures_are_named(messages):
    assert "FOR    ${i}    IN RANGE    2" in actions_named(messages, "start_for")
    assert "IF    ${i} == 1" in actions_named(messages, "start_if")
    assert "ELSE" in actions_named(messages, "start_else")
    assert "EXCEPT    expected" in actions_named(messages, "start_except")
    assert "FINALLY" in actions_named(messages, "start_finally")
    assert "WHILE    ${n} < 1" in actions_named(messages, "start_while")

    iterations = actions_named(messages, "start_iteration")
    assert "ITERATION    ${i} = 0" in iterations
    assert "ITERATION" in iterations  # WHILE iterations assign nothing


def test_branch_containers_are_not_sent(messages):
    assert not {m["action"] for m in messages} & {
        "start_if/else root",
        "start_try/except root",
    }


def test_missing_keyword_is_sent(messages):
    assert actions_named(messages, "start_invalid_keyword") == [
        "This Keyword Does Not Exist"
    ]


def test_pauses_once_for_each_failure(listener):
    """Each of "boom", the missing keyword, "expected" and "deep" pauses once."""
    assert listener.pause_event.clear_count == 4


def test_gui_replays_a_real_run(messages):
    """Every message is handled and the call stack unwinds back to the root."""
    with patch("RobotLiveTrace.gui.dpg") as mock_dpg:
        mock_dpg.add_tree_node.side_effect = itertools.count(1000)
        mock_dpg.does_item_exist.return_value = True
        mock_dpg.get_value.return_value = False

        gui = GUI(queue.Queue())
        gui.themes = dict.fromkeys(
            ["running", "pass", "fail", "log_warn", "log_info", "not_run"], 1
        )

        for message in messages:
            gui.handle_message(message)

    assert gui.active_stack == ["tree_container"]
    assert "for    ${i}    in range    2 " in gui.node_search_text.values()
    assert any("42" in text for text in gui.node_search_text.values())
