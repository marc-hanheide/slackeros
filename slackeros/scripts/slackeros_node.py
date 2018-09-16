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
        '~users', '')
    wl_channels = rospy.get_param(
        '~channels', '')
    topics = rospy.get_param(
        '~topics', '')
    url_prefix = rospy.get_param(
        '~url_prefix', '')
    rospy.loginfo(
        '\n'
        '  running as %s\n'
        '    slack message webhoook: ~webhook =    "%s"\n'
        '    allowed users:          ~users =      "%s"\n'
        '    allowed channels:       ~channels =   "%s"\n'
        '    subscribed topics:      ~topics =     "%s"\n'
        '    URL webhook prefix:     ~url_prefix = "%s"\n' %
        (
            rospy.get_name(),
            hook,
            wl_users,
            wl_channels,
            topics,
            url_prefix
        )
        )
    sc = RosConnector(
        incoming_webhook=hook,
        whitelist_users=wl_users.split(),
        whitelist_channels=wl_channels.split(),
        topics=topics.split(),
        prefix=url_prefix
    )
    sc.run()
