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
    rospy.init_node('slackeros')
    hook = rospy.get_param(
        '~webhook',
        'https://hooks.slack.com/services/'
        'TCTBP6280/BCU8QFBE1/l2B4r7TRzLJJ37zyhXqtICov')
    wl_users = rospy.get_param(
        '~users', [])
    wl_channels = rospy.get_param(
        '~channels', [])
    topics = rospy.get_param(
        '~topics', [])
    print topics
    url_prefix = rospy.get_param(
        '~url_prefix', '')
    sc = RosConnector(
        incoming_webhook=hook,
        whitelist_users=wl_users,
        whitelist_channels=wl_channels,
        topics=topics,
        prefix=url_prefix
    )
    sc.run()
