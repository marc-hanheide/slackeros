#!/usr/bin/env python
from os import _exit, getenv
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
        'XXX/XXX/XXX')
    sender_name = rospy.get_param(
        '~sender_name', getenv('HOSTNAME', rospy.get_name()))
    token = rospy.get_param(
        '~access_token', '')
    upload_images = rospy.get_param(
        '~upload_images', True)
    image_up_channels = rospy.get_param(
        '~image_upload_channels', '')
    wl_users = rospy.get_param(
        '~users', '')
    wl_channels = rospy.get_param(
        '~channels', '')
    topics = rospy.get_param(
        '~topics', '')
    loggers = rospy.get_param(
        '~loggers', '/rosout:error')
    url_prefix = rospy.get_param(
        '~url_prefix', '')
    port = rospy.get_param(
        '~port', 8080)
    rospy.loginfo(
        '\n'
        '  running as %s\n'
        '    sender name:            ~sender_name = "%s"\n'
        '    slack message webhoook: ~webhook =     "%s"\n'
        '    allowed users:          ~users =       "%s"\n'
        '    allowed channels:       ~channels =    "%s"\n'
        '    imgs upload channels:   ~img_up_chns = "%s"\n'
        '    subscribed topics:      ~topics =      "%s"\n'
        '    active loggers:         ~loggers =     "%s"\n'
        '    URL webhook prefix:     ~url_prefix =  "%s"\n'
        '    port:                   ~port = "%d"\n' %
        (
            sender_name,
            rospy.get_name(),
            hook,
            wl_users,
            wl_channels,
            image_up_channels,
            topics,
            loggers,
            url_prefix,
            port
        )
        )
    logger_dict = {}
    for l in loggers.split():
        (n, l) = l.split(':')
        logger_dict[n] = l

    sc = RosConnector(
        incoming_webhook=hook,
        access_token=token,
        upload_images=upload_images,
        whitelist_users=wl_users.split(),
        whitelist_channels=wl_channels.split(),
        image_up_channels=image_up_channels.split(),
        topics=topics.split(),
        loggers=logger_dict,
        prefix=url_prefix,
        sender_name=sender_name
    )
    sc.run(port=port)
