#!/usr/bin/env python
from os import _exit
import signal
import rospy
from slackeros.ros_connector import RosConnector


def __signal_handler(signum, frame):
    print "stopped."
    _exit(signal.SIGTERM)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, __signal_handler)
    rospy.init_node('slack_ros')
    sc = RosConnector(
        incoming_webhook='https://hooks.slack.com/services/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',
        whitelist_users=['mhanheide']
    )
    sc.run()
