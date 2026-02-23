# Robotframework Live Trace

A real-time, cross-platform execution visualization dashboard for Robot Framework.

Built on top of [Dear PyGui](https://github.com/hoffstadt/DearPyGui) and the Robot Framework Listener API (v3), this tool runs a high-performance, hardware-accelerated GUI in a completely isolated process. It allows you to monitor deeply nested keyword call stacks, inspect live arguments, and trace failures exactly as they happen without blocking your test execution.

## Features

* **Live Execution Tree**: Watch your Suites, Tests, and Keywords expand and collapse in real-time.
* **Dedicated Error Feed**: A split-pane chronological feed of all `WARN`, `ERROR`, and `FAIL` logs. Click any error to instantly expand the tree and highlight the exact keyword that caused it.
* **Interactive Tooltips**: Hover over any keyword to see its execution time, status, and input arguments.
* **Execution Control**: Pause and resume the active Robot Framework test run directly from the GUI.
* **Smart Filtering**: Instantly search massive execution trees by keyword name, argument, or log message.
* **Process Isolated**: Runs in a separate `multiprocessing` process, dodging the Python GIL and ensuring your test timings are not affected by GUI rendering overhead.

## Requirements

* Python 3.10+
* Robot Framework >= 7.0 *(Requires the V3 Listener API)*
* Dear PyGui >= 2.2

## Installation

Install the package directly from PyPI:

```bash
uv add robotframework-live-trace
```

or using pip:

```bash
pip install robotframework-live-trace

```

## Usage

You do not need to modify your Robot Framework test files. Simply pass the listener to the `robot` command:

```bash
robot --listener RobotLiveTrace my_tests/

```

The Dear PyGui dashboard will open immediately, and the test execution will begin. When the test suite finishes, the window will remain open so you can inspect the final call stack. Close the window to exit robotframework.

## UI Controls

The top control bar provides several ways to manage large test executions:

* **Pause**: Freezes the Robot Framework execution thread. Uncheck to resume.
* **Auto-Scroll**: Automatically scrolls the tree and error feed to the bottom as new keywords and logs arrive.
* **Auto-Collapse Passed**: When a test or suite finishes with a `PASS` status, it will automatically collapse its tree node to keep the UI clean. Failed nodes will remain expanded.
* **Expand All / Collapse All**: Instantly open or close all currently rendered tree nodes.
* **Filter (Name/Args/Logs)**: Type to instantly hide non-matching keywords. The tree will automatically expand parents to reveal deeply nested matches.

## Contributing

Contributions, issues, and feature requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

### Third-Party Assets
* **Noto Sans Font**: This package bundles the "Noto Sans" font. The font is licensed under the SIL Open Font License, Version 1.1. The full license text can be found in [src/RobotLiveTrace/fonts/OFL.txt](src/RobotLiveTrace/fonts/OFL.txt).