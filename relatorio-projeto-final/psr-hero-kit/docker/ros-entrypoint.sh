#!/bin/bash
# Source ROS and make the student scripts executable (a zip extracted on Windows
# loses the permission bits), then run the command.
set -e
source /opt/ros/noetic/setup.bash
export ROS_PACKAGE_PATH=/ws:/opt/psr:$ROS_PACKAGE_PATH
export PYTHONPATH=/opt/psr/psr_hero/src:$PYTHONPATH
find /ws -name '*.py' ! -perm -u+x -exec chmod +x {} + 2>/dev/null || true
exec "$@"
