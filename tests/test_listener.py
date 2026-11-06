import sys
from datetime import datetime
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from RobotLiveTrace.listener import RobotLiveTrace


@pytest.fixture
def mock_multiprocessing():
    with patch("RobotLiveTrace.listener.multiprocessing") as mock_mp:
        # Setup the mock process to appear alive by default
        mock_process_inst = mock_mp.Process.return_value
        mock_process_inst.is_alive.return_value = True

        # Setup the mock event to be set (not paused) by default
        mock_event_inst = mock_mp.Event.return_value
        mock_event_inst.is_set.return_value = True

        yield mock_mp


@pytest.fixture
def listener(mock_multiprocessing):
    return RobotLiveTrace()


def test_listener_initialization(listener, mock_multiprocessing):
    """Verify listener starts the GUI process and sets up queues."""
    mock_multiprocessing.Queue.assert_called_once()
    mock_multiprocessing.Event.assert_called_once()
    mock_multiprocessing.Process.assert_called_once()
    listener.gui_process.start.assert_called_once()


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
    result = SimpleNamespace(status="FAIL", elapsed_time=timedelta(seconds=0.5))

    listener.end_user_keyword(MagicMock(), MagicMock(), result)

    assert sent_message(listener) == {
        "action": "end_user_keyword",
        "data": None,
        "result": {"status": "FAIL", "elapsed_time": 0.5},
    }


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
