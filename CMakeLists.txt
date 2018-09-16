cmake_minimum_required(VERSION 2.8.3)
project(slackeros)

find_package(catkin REQUIRED COMPONENTS
  message_generation
  rospy
  std_msgs
  std_srvs
  sensor_msgs
)

catkin_python_setup()

## Generate services in the 'srv' folder
add_service_files(
  FILES
  SlashCommand.srv
)

## Generate actions in the 'action' folder
# add_action_files(
#   FILES
#   Action1.action
#   Action2.action
# )

## Generate added messages and services with any dependencies listed here
generate_messages(
  DEPENDENCIES
  std_msgs
  sensor_msgs
)

catkin_package()

install(PROGRAMS
  scripts/slackeros_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

foreach (launch)
    install(DIRECTORY ${dir}/
    DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/${dir})
endforeach(dir)
