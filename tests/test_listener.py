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


def test_listener_sends_start_suite(listener):
    """Verify start_suite puts correct message on queue."""
    data = MagicMock()
    data.to_dict.return_value = {"name": "My Suite"}
    result = MagicMock()
    result.to_dict.return_value = {}

    listener.start_suite(data, result)

    listener.message_queue.put.assert_called_once()
    msg = listener.message_queue.put.call_args[0][0]
    assert msg["action"] == "start_suite"
    assert msg["data"]["name"] == "My Suite"


def test_listener_sends_log_message(listener):
    """Verify log_message puts correct message on queue."""
    msg_obj = MagicMock()
    msg_obj.to_dict.return_value = {"message": "Hello", "level": "INFO"}

    listener.log_message(msg_obj)

    listener.message_queue.put.assert_called_once()
    msg = listener.message_queue.put.call_args[0][0]
    assert msg["action"] == "log_message"
    assert msg["result"]["message"] == "Hello"


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
