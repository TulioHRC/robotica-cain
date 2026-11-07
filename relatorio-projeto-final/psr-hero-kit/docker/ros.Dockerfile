# ROS 1 Noetic for the exercises: roscore, rospy, roslaunch, the rostopic / rosnode /
# rosparam tools and the common messages, without the C++ toolchain. Runs on amd64
# and arm64. The bridge to the simulator lives in /opt/psr.
FROM ubuntu:focal

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUNBUFFERED=1

# gfortran-9 is listed only to satisfy libboost-all-dev (pulled by rosbag, which rostopic
# needs) with a small package: otherwise apt picks flang-18, a 1 GB Fortran compiler.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
         | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros/ubuntu focal main" \
         > /etc/apt/sources.list.d/ros1.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
         ros-noetic-rospy ros-noetic-roslaunch ros-noetic-rostopic ros-noetic-rosnode \
         ros-noetic-rosparam ros-noetic-rosmsg ros-noetic-rosout \
         ros-noetic-std-msgs ros-noetic-geometry-msgs ros-noetic-nav-msgs ros-noetic-sensor-msgs \
         python3-numpy gfortran-9 \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* /usr/include/boost

COPY ros/psr_hero /opt/psr/psr_hero
COPY docker/ros-entrypoint.sh /ros-entrypoint.sh
RUN chmod +x /ros-entrypoint.sh /opt/psr/psr_hero/scripts/*.py

WORKDIR /ws
ENTRYPOINT ["/ros-entrypoint.sh"]
CMD ["bash"]
