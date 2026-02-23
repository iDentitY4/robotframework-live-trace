import enum
import queue
from importlib.resources import files
from multiprocessing.synchronize import Event
from typing import Any

import dearpygui.dearpygui as dpg  # type: ignore

from RobotLiveTrace.message import Message
from RobotLiveTrace.version import AUTHOR, VERSION


class FontSize(enum.IntEnum):
    TINY = 10
    SMALL = 14
    NORMAL = 18
    LARGE = 24

    def __str__(self) -> str:
        return f"{self.name.title()} ({self.value}px)"


class GUI:
    def __init__(
        self, message_queue: queue.Queue[Message], pause_event: Event | None = None
    ) -> None:
        self.message_queue = message_queue
        self.pause_event = pause_event

        self.all_nodes: list[int | str] = []
        self.node_parents: dict[int | str, Any] = {}
        self.node_search_text: dict[int | str, str] = {}
        self.node_themes: dict[int | str, int] = {}
        self.node_data: dict[int | str, dict[str, Any]] = {}
        self.active_stack: list[int | str] = ["tree_container"]

        self.font_sizes: dict[FontSize, int | str] = {}
        self.default_font_size = FontSize.NORMAL
        self.themes: dict[str, int] = {}

        self.needs_filter_update = False
        self.items_added_this_frame = False

        self.prefixes = {
            "start_suite": "[SUITE]",
            "start_test": "[TEST]",
            "start_user_keyword": "[USER-KW]",
            "start_library_keyword": "[LIB-KW]",
        }

    def setup_icons(self) -> None:
        pass
        # if sys.platform == "win32":
        #     icon_file = files("RobotLiveTrace").joinpath("icons/app_icon.ico")
        #     dpg.set_viewport_small_icon(str(icon_file))

    def setup_fonts(self) -> None:
        font_file = files("RobotLiveTrace").joinpath("fonts/NotoSans-Regular.ttf")

        # Setup fonts
        with dpg.font_registry():
            font_path = str(font_file)

            for size in FontSize:
                self.font_sizes[size] = dpg.add_font(font_path, size.value)

    def setup_themes(self) -> None:
        with dpg.theme() as self.themes["running"]:
            with dpg.theme_component(dpg.mvTreeNode):
                # Light Blue text for running keywords
                dpg.add_theme_color(dpg.mvThemeCol_Text, (100, 200, 255, 255))

        with dpg.theme() as self.themes["pass"]:
            with dpg.theme_component(dpg.mvTreeNode):
                # Green text for passed keywords
                dpg.add_theme_color(dpg.mvThemeCol_Text, (50, 255, 50, 255))

        with dpg.theme() as self.themes["fail"]:
            with dpg.theme_component(dpg.mvTreeNode):
                # Red text for failed keywords
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 50, 50, 255))

        with dpg.theme() as self.themes["log_warn"]:
            with dpg.theme_component(dpg.mvTreeNode):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 200, 50, 255))

        with dpg.theme() as self.themes["log_info"]:
            with dpg.theme_component(dpg.mvTreeNode):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (180, 180, 180, 255))

        with dpg.theme() as self.themes["highlight"]:
            with dpg.theme_component(dpg.mvAll):
                # Bright Yellow text so it pops out instantly
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 0, 255))

    def setup_layout(self) -> None:
        with dpg.window(
            label="Call Stack",
            tag="main_window",
            width=1400,
            height=800,
            no_close=True,
            no_collapse=True,
            no_resize=True,
            no_move=True,
            no_title_bar=True,
        ):
            with dpg.menu_bar():
                with dpg.menu(label="Menu"):
                    with dpg.menu(
                        label="Settings",
                    ):
                        dpg.add_combo(
                            [str(size) for size in self.font_sizes],
                            label="Font Size",
                            default_value=str(self.default_font_size),
                            width=150,
                            callback=self.change_font_size,
                        )

                    dpg.add_menu_item(
                        label="About RobotLiveTrace", callback=self.show_about
                    )
                    dpg.add_menu_item(
                        label="About Dearpygui",
                        callback=lambda: dpg.show_tool(dpg.mvTool_About),
                    )
                    dpg.add_menu_item(
                        label="Exit", callback=lambda: dpg.stop_dearpygui()
                    )

            with dpg.group(horizontal=True):
                dpg.add_checkbox(label="Pause Execution", callback=self.toggle_pause)
                dpg.add_text(" | ")
                dpg.add_checkbox(
                    label="Auto-Scroll", tag="auto_scroll_toggle", default_value=True
                )
                dpg.add_text(" | ")
                dpg.add_checkbox(
                    label="Auto-Collapse Passed",
                    tag="auto_collapse_toggle",
                    default_value=True,
                )
                dpg.add_text(" | ")
                dpg.add_button(label="Expand All", callback=self.expand_all)
                dpg.add_button(label="Collapse All", callback=self.collapse_all)

            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    label="Filter (Name/Args)",
                    tag="filter_input",
                    callback=self.apply_filter,
                    width=300,
                )

            dpg.add_separator()

            with dpg.group(horizontal=True):
                with dpg.child_window(
                    tag="tree_container", width=900, resizable_x=True
                ):
                    pass

                with dpg.child_window(tag="error_feed_container"):
                    dpg.add_text("Error & Warning Feed", color=(255, 100, 100))
                    dpg.add_separator()

    def setup_extras(self) -> None:
        with dpg.window(
            label="About RobotLiveTrace",
            tag="about_window",
            width=400,
            pos=(200, 200),
            show=False,
            no_resize=True,
        ):
            dpg.add_text("RobotLiveTrace", color=(100, 200, 255), wrap=380)
            dpg.add_text(
                "A real-time execution trace viewer for Robot Framework, built with DearPyGui.",
                wrap=380,
            )
            dpg.add_separator()
            dpg.add_text(f"Version: {VERSION}")
            dpg.add_separator()
            dpg.add_text("Authors:", color=(100, 200, 255))
            dpg.add_text(f"{AUTHOR}")

    #
    # Callbacks
    #
    def toggle_pause(self, sender: int, app_data: Any):
        if self.pause_event is None:
            return

        if app_data:
            self.pause_event.clear()  # Block the listener process
        else:
            self.pause_event.set()  # Resume the listener process

    def expand_all(self, sender: int, app_data: Any):
        for node_id in self.all_nodes:
            dpg.set_value(node_id, True)

    def collapse_all(self, sender: int, app_data: Any):
        for node_id in self.all_nodes:
            dpg.set_value(node_id, False)

    def apply_filter(self, sender: int | None = None, app_data: Any | None = None):
        search_string = dpg.get_value("filter_input").lower()

        if not search_string:
            for node_id in self.all_nodes:
                dpg.show_item(node_id)
            return

        matches = set()
        for node_id, txt in self.node_search_text.items():
            if search_string in txt:
                matches.add(node_id)

        visible_set = set(matches)
        for node_id in matches:
            curr = self.node_parents.get(node_id)
            while curr and curr not in ("tree_container", "main_window"):
                visible_set.add(curr)
                dpg.set_value(
                    curr, True
                )  # Auto-expand the parent so we can see the match
                curr = self.node_parents.get(curr)

        for node_id in self.all_nodes:
            if node_id in visible_set:
                dpg.show_item(node_id)
            else:
                dpg.hide_item(node_id)

    def jump_to_node(self, sender: int, app_data: Any, user_data: Any):
        target_node = user_data

        if target_node is None or not dpg.does_item_exist(target_node):
            return

        if app_data:
            dpg.bind_item_theme(target_node, self.themes["highlight"])

            curr = self.node_parents.get(target_node)
            while curr and curr not in ("tree_container", "main_window"):
                dpg.set_value(curr, True)
                curr = self.node_parents.get(curr)

            dpg.focus_item(target_node)
        else:
            original_theme = self.node_themes.get(target_node, self.themes["running"])
            dpg.bind_item_theme(target_node, original_theme)

    def change_font_size(self, sender, app_data):
        if app_data is None:
            return

        for size, font_id in self.font_sizes.items():
            if str(size) == app_data:
                dpg.bind_font(font_id)
                dpg.bind_item_font("main_window", font_id)
                dpg.bind_item_font("about_window", font_id)
                break

    def show_about(self, sender: int, app_data: Any):
        dpg.show_item("about_window")

    #
    # Message handling
    #

    def handle_start(
        self,
        action: str,
        data: dict[str, Any],
    ) -> None:
        name = data.get("name", "Unknown")
        args = data.get("args", [])

        prefix = self.prefixes.get(action, "[*]")
        parent_id = self.active_stack[-1]
        base_label = f"{prefix} {name}"

        node_id = dpg.add_tree_node(
            label=base_label, parent=parent_id, default_open=True
        )
        dpg.bind_item_theme(node_id, self.themes["running"])
        self.node_themes[node_id] = self.themes["running"]

        self.all_nodes.append(node_id)
        self.node_parents[node_id] = parent_id
        self.node_search_text[node_id] = f"{name} {' '.join(args)}".lower()
        self.needs_filter_update = True
        self.items_added_this_frame = True

        with dpg.tooltip(node_id):
            dpg.add_text(
                f"Type: {action.replace('start_', '').replace('_', ' ').title()}"
            )
            dpg.add_text(f"Name: {name}")

            if args:
                dpg.add_text(f"Args: {', '.join(args)}")

            status_id = dpg.add_text("Status: Running...")
            time_id = dpg.add_text("Elapsed Time: Running...")
            dpg.add_separator()

        self.active_stack.append(node_id)

        self.node_data[node_id] = {
            "label": base_label,
            "status_id": status_id,
            "time_id": time_id,
        }

    def handle_log(self, result: dict[str, Any]) -> None:
        if len(self.active_stack) <= 1:
            return

        parent_id = self.active_stack[-1]

        level = result.get("level", "<UNKNOWN>")
        full_txt = result.get("message", "<MISSING LOG MESSAGE>")
        timestamp = result.get("timestamp", "<NO TIMESTAMP>")

        # Truncate text for the tree label so it doesn't break the UI layout
        # Replace newlines with spaces for a cleaner single-line preview
        clean_txt = full_txt.replace("\n", " ")
        display_txt = clean_txt if len(clean_txt) < 80 else clean_txt[:77] + "..."

        node_id = dpg.add_tree_node(
            label=f"[{level}] {display_txt}",
            parent=parent_id,
            leaf=True,
        )

        if level in ["WARN", "WARNING"]:
            dpg.bind_item_theme(node_id, self.themes["log_warn"])
            self.node_themes[node_id] = self.themes["log_warn"]
        elif level in ["FAIL", "ERROR"]:
            dpg.bind_item_theme(node_id, self.themes["fail"])
            self.node_themes[node_id] = self.themes["fail"]
        else:
            dpg.bind_item_theme(node_id, self.themes["log_info"])
            self.node_themes[node_id] = self.themes["log_info"]

        self.all_nodes.append(node_id)
        self.node_parents[node_id] = parent_id
        self.node_search_text[node_id] = f"{level} {full_txt}".lower()
        self.needs_filter_update = True
        self.items_added_this_frame = True

        with dpg.tooltip(node_id):
            dpg.add_text(f"Level: {level}")
            dpg.add_text(f"Time: {timestamp}")
            dpg.add_text(full_txt, wrap=600)
            dpg.add_separator()

        # Error feed
        if level in ["FAIL", "ERROR", "WARN", "WARNING"]:
            parent_data = self.node_data.get(parent_id, {"label": "Unknown context"})
            context_name = parent_data["label"]

            error_item = dpg.add_selectable(
                label=f"[{level}] {context_name}",
                callback=self.jump_to_node,
                user_data=node_id,
                parent="error_feed_container",
            )

            if level in ["FAIL", "ERROR"]:
                dpg.bind_item_theme(error_item, self.themes["fail"])
            else:
                dpg.bind_item_theme(error_item, self.themes["log_warn"])

            dpg.add_text(clean_txt, wrap=440, parent="error_feed_container")
            dpg.add_separator(parent="error_feed_container")

    def handle_end(self, action: str, result: dict[str, Any]) -> None:
        if len(self.active_stack) <= 1:
            return

        node_id = self.active_stack.pop()
        node = self.node_data.get(node_id)

        if node is None or not dpg.does_item_exist(node_id):
            return

        status = result.get("status", "UNKNOWN")
        elapsed = result.get("elapsed_time", 0.0)

        if status == "PASS":
            dpg.bind_item_theme(node_id, self.themes["pass"])
            self.node_themes[node_id] = self.themes["pass"]

            if dpg.get_value("auto_collapse_toggle"):
                dpg.set_value(node_id, False)
        else:
            dpg.bind_item_theme(node_id, self.themes["fail"])
            self.node_themes[node_id] = self.themes["fail"]

        dpg.set_value(node["status_id"], f"Status: {status}")
        dpg.set_value(node["time_id"], f"Elapsed Time: {elapsed} s")

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="RobotLiveTrace", width=1400, height=800)
        dpg.setup_dearpygui()

        self.setup_icons()
        self.setup_fonts()
        self.setup_themes()
        self.setup_layout()
        self.setup_extras()

        dpg.set_primary_window("main_window", True)
        default_font = self.font_sizes[self.default_font_size]
        dpg.bind_item_font("main_window", default_font)
        dpg.bind_item_font("about_window", default_font)

        dpg.show_viewport()

        while dpg.is_dearpygui_running():
            self.needs_filter_update = False
            self.items_added_this_frame = False

            try:
                while True:
                    msg: Message = self.message_queue.get_nowait()
                    action = msg.get("action", "unknown")
                    data = msg.get("data", None)
                    result = msg.get("result", None)

                    if action.startswith("start_") and data is not None:
                        self.handle_start(
                            action,
                            data=data,
                        )
                    elif action == "log_message" and result is not None:
                        self.handle_log(result)
                    elif action.startswith("end_") and result is not None:
                        self.handle_end(action, result)
            except queue.Empty:
                pass

            if self.needs_filter_update and dpg.get_value("filter_input"):
                self.apply_filter()

            if self.items_added_this_frame and dpg.get_value("auto_scroll_toggle"):
                dpg.set_y_scroll("tree_container", 999999)
                dpg.set_y_scroll("error_feed_container", 999999)

            dpg.render_dearpygui_frame()

        if self.pause_event is not None:
            self.pause_event.set()  # Ensure listener isn't stuck waiting if GUI is closed

        dpg.destroy_context()


def run_gui(q: queue.Queue[Message], pause_event: Event | None = None):
    gui = GUI(q, pause_event)
    gui.run()


if __name__ == "__main__":
    run_gui(queue.Queue())
