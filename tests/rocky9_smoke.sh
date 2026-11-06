#!/usr/bin/env bash
# Checks that the real GUI starts on Rocky Linux 9. Run it as root inside a Rocky 9
# container, from a writable copy of the repository:
#
#   podman run --rm -v "$PWD:/repo:Z" -w /repo docker.io/rockylinux/rockylinux:9 \
#       bash tests/rocky9_smoke.sh
set -euo pipefail

work_dir=$(mktemp -d)

dnf -q -y install python3.12 python3.12-pip xorg-x11-server-Xvfb \
    mesa-dri-drivers mesa-libGL libglvnd-glx libX11 libXrandr libXinerama \
    libXcursor libXi

python3.12 -m venv "$work_dir/venv"
"$work_dir/venv/bin/pip" install --quiet . "dearpygui==2.0.0"

cat > "$work_dir/smoke.robot" <<'ROBOT'
*** Test Cases ***
Smoke
    Log    hello
ROBOT

Xvfb :99 -screen 0 1420x820x24 &
xvfb_pid=$!
trap 'kill "$xvfb_pid"' EXIT
sleep 1

# Once the tests finish, Robot waits for the GUI window to be closed. The timeout
# ending the run (exit code 137) therefore means the GUI started and stayed open.
# SIGKILL also stops the GUI process, which would otherwise outlive Robot.
exit_code=0
cd "$work_dir"
DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 PYTHONUNBUFFERED=1 \
    timeout -s KILL 20 venv/bin/python -m robot --listener RobotLiveTrace \
    --output NONE --log NONE --report NONE smoke.robot > run.log 2>&1 \
    || exit_code=$?
cat run.log

if [[ $exit_code -ne 137 ]] || ! grep -q "RobotLiveTrace is open" run.log; then
    echo "GUI did not stay open (robot exit code: $exit_code)" >&2
    exit 1
fi

echo "GUI started and stayed open"
