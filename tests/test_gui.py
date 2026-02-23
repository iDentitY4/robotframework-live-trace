import queue
from unittest.mock import MagicMock, patch

import pytest

from RobotLiveTrace.gui import GUI


@pytest.fixture
def mock_dpg():
    with patch("RobotLiveTrace.gui.dpg") as mock:
        yield mock


@pytest.fixture
def gui_instance(mock_dpg):
    q = queue.Queue()
    evt = MagicMock()
    gui = GUI(q, evt)
    # Pre-populate themes to avoid KeyErrors during tests
    gui.themes = {
        "running": 10,
        "pass": 11,
        "fail": 12,
        "log_warn": 13,
        "log_info": 14,
        "highlight": 15,
    }
    return gui


def test_gui_handle_start_adds_node(gui_instance, mock_dpg):
    """Verify handle_start adds a tree node and updates stack."""
    mock_dpg.add_tree_node.return_value = 123
    data = {"name": "Keyword", "args": ["arg1"]}

    gui_instance.handle_start("start_user_keyword", data)

    mock_dpg.add_tree_node.assert_called()
    assert 123 in gui_instance.all_nodes
    assert gui_instance.active_stack[-1] == 123
    assert gui_instance.node_search_text[123] == "keyword arg1"


def test_gui_handle_log_adds_leaf_node(gui_instance, mock_dpg):
    """Verify handle_log adds a leaf node and does not push to stack."""
    # Setup a parent node
    gui_instance.active_stack = ["root", 50]
    gui_instance.node_data[50] = {"label": "Parent"}

    mock_dpg.add_tree_node.return_value = 51
    result = {"level": "INFO", "message": "Log info", "timestamp": "12:00"}

    gui_instance.handle_log(result)

    mock_dpg.add_tree_node.assert_called()
    # Should be leaf, so stack shouldn't change
    assert gui_instance.active_stack[-1] == 50
    assert 51 in gui_instance.all_nodes


def test_gui_handle_log_error_adds_to_feed(gui_instance, mock_dpg):
    """Verify error logs are added to the error feed."""
    gui_instance.active_stack = ["root", 50]
    gui_instance.node_data[50] = {"label": "Parent"}

    result = {"level": "FAIL", "message": "Something broke", "timestamp": "12:00"}

    gui_instance.handle_log(result)

    # Check that it added to error feed container
    assert mock_dpg.add_selectable.called
    assert mock_dpg.add_selectable.call_args[1]["parent"] == "error_feed_container"


def test_gui_handle_end_updates_status(gui_instance, mock_dpg):
    """Verify handle_end pops stack and updates status text."""
    # Setup stack with a node
    gui_instance.active_stack = ["root", 100]
    gui_instance.node_data[100] = {
        "label": "My Keyword",
        "status_id": 200,
        "time_id": 201,
    }
    mock_dpg.does_item_exist.return_value = True

    result = {"status": "PASS", "elapsed_time": 0.5}
    gui_instance.handle_end("end_user_keyword", result)

    # Stack should pop
    assert gui_instance.active_stack == ["root"]
    # Status text updated
    mock_dpg.set_value.assert_any_call(200, "Status: PASS")
    # Theme updated to pass
    mock_dpg.bind_item_theme.assert_called_with(100, gui_instance.themes["pass"])


def test_gui_apply_filter(gui_instance, mock_dpg):
    """Verify filter shows/hides items based on search text."""
    gui_instance.all_nodes = [1, 2, 3]
    gui_instance.node_search_text = {1: "login user", 2: "logout", 3: "check balance"}
    # Simple hierarchy: all under root
    gui_instance.node_parents = {1: "root", 2: "root", 3: "root"}

    # Search for "log" -> matches 1 (login) and 2 (logout)
    mock_dpg.get_value.return_value = "log"

    gui_instance.apply_filter()

    mock_dpg.show_item.assert_any_call(1)
    mock_dpg.show_item.assert_any_call(2)
    mock_dpg.hide_item.assert_any_call(3)


def test_gui_toggle_pause(gui_instance):
    """Verify toggle_pause controls the multiprocessing event."""
    # Pause (checkbox=True) -> clear event
    gui_instance.toggle_pause(None, True)
    gui_instance.pause_event.clear.assert_called_once()

    # Resume (checkbox=False) -> set event
    gui_instance.toggle_pause(None, False)
    gui_instance.pause_event.set.assert_called_once()


def test_gui_expand_collapse_all(gui_instance, mock_dpg):
    """Verify expand/collapse all sets value for all nodes."""
    gui_instance.all_nodes = [10, 20]

    gui_instance.expand_all(None, None)
    mock_dpg.set_value.assert_any_call(10, True)
    mock_dpg.set_value.assert_any_call(20, True)

    mock_dpg.reset_mock()

    gui_instance.collapse_all(None, None)
    mock_dpg.set_value.assert_any_call(10, False)
    mock_dpg.set_value.assert_any_call(20, False)
