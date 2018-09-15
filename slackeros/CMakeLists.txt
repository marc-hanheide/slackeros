cmake_minimum_required(VERSION 2.8.3)
project(slackeros)

find_package(catkin REQUIRED COMPONENTS)

catkin_python_setup()

catkin_package()

install(PROGRAMS
  scripts/slackeros.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
