import sys
from datetime import datetime
from datetime import timedelta
from importlib.metadata import version
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import RobotLiveTrace as RobotLiveTraceModule
from RobotLiveTrace.listener import RobotLiveTrace


@pytest.fixture
def mock_multiprocessing():
    with patch("RobotLiveTrace.listener.multiprocessing") as mock_mp:
        # Setup the mock process to appear alive by default
        mock_process_inst = mock_mp.Process.return_value
        mock_process_inst.is_alive.return_value = True

        # Setup the mock event to be set (not paused) by default
        mock_mp.Event.side_effect = lambda: MagicMock(**{"is_set.return_value": True})

        yield mock_mp


@pytest.fixture
def listener(mock_multiprocessing):
    return RobotLiveTrace()


def test_package_exposes_version():
    assert RobotLiveTraceModule.__version__ == version("robotframework-live-trace")


def test_listener_initialization(listener, mock_multiprocessing):
    """Verify listener starts the GUI process and sets up queues."""
    mock_multiprocessing.Queue.assert_called_once()
    assert mock_multiprocessing.Event.call_count == 2
    mock_multiprocessing.Process.assert_called_once()
    listener.gui_process.start.assert_called_once()


def make_result(status, id="s1-t1-k1", elapsed=0.0):
    return SimpleNamespace(
        status=status, id=id, elapsed_time=timedelta(seconds=elapsed)
    )


def sent_message(listener):
    listener.message_queue.put.assert_called_once()
    return listener.message_queue.put.call_args[0][0]


def test_listener_sends_start_suite(listener):
    """Verify start_suite only sends the suite name."""
    listener.start_suite(SimpleNamespace(name="My Suite"), MagicMock())

    assert sent_message(listener) == {
        "action": "start_suite",
        "data": {"name": "My Suite"},
        "result": None,
    }


def test_listener_converts_keyword_args_to_strings(listener):
    """Verify non-string arguments reach the GUI as strings."""
    data = SimpleNamespace(name="Log", args=("text", 42))

    listener.start_library_keyword(data, MagicMock(), MagicMock())

    assert sent_message(listener)["data"] == {"name": "Log", "args": ["text", "42"]}


def test_listener_sends_end_status_and_elapsed_time(listener):
    """Verify end events send the status and elapsed seconds."""
    result = make_result("FAIL", elapsed=0.5)

    listener.end_user_keyword(MagicMock(), MagicMock(), result)

    assert sent_message(listener) == {
        "action": "end_user_keyword",
        "data": None,
        "result": {"status": "FAIL", "elapsed_time": 0.5},
    }


def test_listener_sends_invalid_keyword(listener):
    """Verify keywords that can't be found are sent to the GUI."""
    data = SimpleNamespace(name="Missing")

    listener.start_invalid_keyword(data, MagicMock(), MagicMock())

    assert sent_message(listener)["action"] == "start_invalid_keyword"


@pytest.mark.parametrize(
    ("data", "action", "name"),
    [
        (
            SimpleNamespace(type="ITERATION", assign={"${i}": 1, "${j}": 2}),
            "start_iteration",
            "ITERATION    ${i} = 1, ${j} = 2",
        ),
        (SimpleNamespace(type="ITERATION"), "start_iteration", "ITERATION"),
    ],
)
def test_listener_names_iterations(listener, data, action, name):
    """Verify iterations are labelled with their values, if they have any."""
    listener.start_body_item(data, MagicMock())

    assert sent_message(listener)["action"] == action
    assert sent_message(listener)["data"] == {"name": name}


@pytest.mark.parametrize("item_type", ["IF/ELSE ROOT", "TRY/EXCEPT ROOT"])
def test_listener_skips_branch_containers(listener, item_type):
    """Verify IF and TRY roots aren't sent, only their branches."""
    data = SimpleNamespace(type=item_type)

    listener.start_body_item(data, MagicMock())
    listener.end_body_item(data, make_result("PASS"))

    listener.message_queue.put.assert_not_called()


def end_keyword(listener, result):
    listener.end_library_keyword(MagicMock(), MagicMock(), result)


def test_pause_on_failure_is_off_by_default(listener):
    listener.pause_on_failure_event.is_set.return_value = False

    end_keyword(listener, make_result("FAIL"))

    listener.pause_event.clear.assert_not_called()


def test_pause_on_failure_pauses_after_sending_the_failure(listener):
    """Verify the GUI can show the failure that caused the pause."""
    calls = MagicMock()
    calls.attach_mock(listener.message_queue.put, "put")
    calls.attach_mock(listener.pause_event.clear, "clear")

    end_keyword(listener, make_result("FAIL"))

    assert [name for name, _, _ in calls.mock_calls] == ["put", "clear"]


def test_pause_on_failure_ignores_passing_keywords(listener):
    end_keyword(listener, make_result("PASS"))

    listener.pause_event.clear.assert_not_called()


def test_pause_on_failure_pauses_once_as_failure_reaches_parents(listener):
    end_keyword(listener, make_result("FAIL", id="s1-t1-k1-k1-k2"))
    end_keyword(listener, make_result("FAIL", id="s1-t1-k1-k1"))
    end_keyword(listener, make_result("FAIL", id="s1-t1-k1"))

    listener.pause_event.clear.assert_called_once()


def test_pause_on_failure_pauses_again_for_a_new_failure(listener):
    end_keyword(listener, make_result("FAIL", id="s1-t1-k1"))
    end_keyword(listener, make_result("FAIL", id="s1-t1-k2"))
    end_keyword(listener, make_result("FAIL", id="s1-t1-k10"))

    assert listener.pause_event.clear.call_count == 3


def test_pause_on_failure_ignores_test_and_suite_ends(listener):
    """Verify a test or suite that failed without a failing keyword doesn't pause."""
    listener.end_test(MagicMock(), make_result("FAIL"))
    listener.end_suite(MagicMock(), make_result("FAIL"))

    listener.pause_event.clear.assert_not_called()


def test_listener_sends_log_message(listener):
    """Verify log_message sends the level, text and timestamp."""
    message = SimpleNamespace(
        level="INFO", message="Hello", timestamp=datetime(2026, 1, 2, 3, 4, 5)
    )

    listener.log_message(message)

    msg = sent_message(listener)
    assert msg["action"] == "log_message"
    assert msg["result"] == {
        "level": "INFO",
        "message": "Hello",
        "timestamp": "2026-01-02T03:04:05",
    }


def test_listener_omits_missing_log_timestamp(listener):
    """Verify a message without a timestamp leaves the GUI's default in place."""
    listener.log_message(SimpleNamespace(level="INFO", message="Hello", timestamp=None))

    assert "timestamp" not in sent_message(listener)["result"]


def test_listener_explains_dearpygui_import_failure(mock_multiprocessing):
    """Verify a Dear PyGui import failure tells the user how to fix it."""
    with patch.dict(sys.modules, {"RobotLiveTrace.gui": None}):
        with pytest.raises(ImportError, match="dearpygui==2.0.0"):
            RobotLiveTrace()

    mock_multiprocessing.Process.assert_not_called()


def test_listener_pauses_execution(listener):
    """Verify listener waits when pause event is cleared."""
    # Mock event: initially False (paused), then True (resumed)
    listener.pause_event.is_set.side_effect = [False, True]

    listener.start_test(MagicMock(), MagicMock())

    # Should have called wait() because is_set() returned False once
    listener.pause_event.wait.assert_called_with(timeout=0.2)
    # Should still send message after waiting
    listener.message_queue.put.assert_called()


def test_listener_stops_sending_if_process_dead(listener):
    """Verify listener does not send messages if GUI process is dead."""
    listener.gui_process.is_alive.return_value = False

    listener.start_test(MagicMock(), MagicMock())

    listener.message_queue.put.assert_not_called()


def test_listener_close_joins_process(listener):
    """Verify close() joins the GUI process."""
    listener.close()
    listener.gui_process.join.assert_called_once()
