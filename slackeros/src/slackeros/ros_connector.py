import web

from pprint import pformat
from os import _exit
import signal
from base_connector import SlackConnector
import rospy
from std_msgs.msg import String
from std_srvs.srv import Empty
from rostopic import get_topic_class
from rosservice import get_service_class_by_name
from rosservice import get_service_list, call_service
from threading import Thread
from roslib.message import strify_message
from slackeros.srv import SlashCommand
import argparse
from StringIO import StringIO
import roslib
import rosmsg


def __signal_handler(signum, frame):
    print "stopped."
    _exit(signal.SIGTERM)


class RosConnector(SlackConnector):

    ROS_PREFIX = '/slackeros'

    def __init__(
        self,
        incoming_webhook=None,
        whitelist_channels=[],
        whitelist_users=[],
        topics=[ROS_PREFIX + '/to_slack'],
        prefix=''
    ):
        self.incoming_webhook = incoming_webhook
        self.whitelist_channels = set(whitelist_channels)
        self.whitelist_users = set(whitelist_users)
        self.topics = set(topics)

        SlackConnector.__init__(
            self, incoming_webhook,
            whitelist_channels, whitelist_users, prefix)

        self.slash_pub = rospy.Publisher('~slash_cmd', String, queue_size=1)
        self.subs = {}

        for t in self.topics:
            print 'topic ', t
            self._subscribe(t)

    def _subscribe(self, topic):
        class DynSub(Thread):

            def __init__(self, topic, cb, connected_cb=None):
                Thread.__init__(self)
                self.topic = topic
                self.cb = cb
                self.connected_cb = connected_cb

            def run(self):
                rospy.loginfo(
                    'trying to connect to topic %s' %
                    self.topic)
                msg_class, real_topic, _ = get_topic_class(
                    self.topic, blocking=True)
                sub = rospy.Subscriber(
                    real_topic, msg_class, self.cb,
                    callback_args=(self.topic))
                rospy.loginfo(
                    'connected to topic %s' %
                    self.topic)
                if self.connected_cb:
                    self.connected_cb(self.topic, sub)

        def __connected(topic, sub):
            self.subs[topic] = sub

        DynSub(topic, self.to_slack_cb, __connected).start()

    def _unsubscribe(self, topic):
        if topic in self.subs:
            self.subs[topic].unregister()
            del self.subs[topic]

    def to_slack_cb(self, msg, topic):
        d = strify_message(msg)
        rospy.loginfo('new message to go to Slack: %s' % d)
        self.send({
            'text': '_New Information on topic %s_' % topic,
            'attachments': [
                {
                    'text': "```\n%s\n```" % d,
                    'author_name': topic
                }
            ]
        })

    def _rostopic(self, args):
        parser = argparse.ArgumentParser(prog='/rostopic')
        subparsers = parser.add_subparsers(dest='cmd',
                                           help='sub-command')
        subparsers.add_parser('list', help='show topics')
        subparsers.add_parser(
            'subscribe', help='subscribe to topic: /rostopic subscribe <topic>'
            ).add_argument(
            'topic', help='topic to suscribe to'
            )
        subparsers.add_parser(
            'unsubscribe', help='unsubscribe from topic:'
            ' /rostopic unsubscribe <topic>'
            ).add_argument(
            'topic', help='topic unsubscribe from'
            )

        try:
            args = parser.parse_args(args)
            print args
        except SystemExit:
            return '```\n%s\n```' % parser.format_help()

        if args.cmd == 'subscribe':
            self._subscribe(args.topic)
            return 'subscribing to `%s`' % args.topic
        elif args.cmd == 'unsubscribe':
            self._unsubscribe(args.topic)
            return 'unsubscribing from `%s`' % args.topic
        elif args.cmd == 'list':
            topics = rospy.get_published_topics()
            tops = [('%s [%s]' % (t[0], t[1])) for t in topics]
            print tops
            return {
                'attachments': [
                    {
                        'text': (
                            '*Currently published topics:*\n```\n%s\n```'
                            % '\n'.join(tops)),
                        'author_name': 'ROS master'
                    },
                    {
                        'text': (
                            '*Currently subscribed by'
                            ' Slack*:\n```\n%s\n```'
                            % '\n'.join(self.subs)),
                        'author_name': 'slackeros'
                    }
                ],
                'text': '_Topics:_'
            }
        else:
            return help_string

    def __call_service(self, service_name, service_args, service_class=None):
        import std_msgs.msg

        if service_class is None:
            service_class = get_service_class_by_name(service_name)
        request = service_class._request_class()
        try:
            now = rospy.get_rostime()
            keys = {'now': now, 'auto': std_msgs.msg.Header(stamp=now)}
            roslib.message.fill_message_args(request, service_args, keys=keys)
        except roslib.message.ROSMessageException, e:
            def argsummary(args):
                if type(args) in [tuple, list]:
                    return '\n'.join(
                        [
                            ' * %s (type %s)' % (a, type(a).__name__)
                            for a in args])
                else:
                    return ' * %s (type %s)' % (args, type(args).__name__)

            return (
                "Incompatible arguments to call service:\n%s\n"
                "Provided arguments are:\n%s\n\nService arguments are: [%s]"
                % (
                    e, argsummary(service_args),
                    roslib.message.get_printable_message_args(request)))
        try:
            return rospy.ServiceProxy(
                service_name, service_class)(request)
        except rospy.ServiceException, e:
            return str(e)
        except roslib.message.SerializationError, e:
            return (
                "Unable to send request."
                " One of the fields has an incorrect type:\n"
                "  %s\n\nsrv file:\n%s"
                % (
                    e,
                    rosmsg.get_srv_text(service_class._type)))
        except rospy.ROSSerializationException, e:
            return (
                "Unable to send request."
                " One of the fields has an incorrect type:\n"
                "  %s\n\nsrv file:\n%s" % (
                    e, rosmsg.get_srv_text(service_class._type)))

    def _rosservice(self, args):
        parser = argparse.ArgumentParser(prog='/rosservice')
        subparsers = parser.add_subparsers(dest='cmd',
                                           help='sub-command')
        subparsers.add_parser('list', help='show services')
        subparsers.add_parser(
            'call', help='call server: /rosservice call <service> [<args>]'
            ).add_argument(
            'service', help='topic to suscribe to'
            )

        try:
            args, additonal_args = parser.parse_known_args(args)
        except SystemExit:
            return '```\n%s\n```' % parser.format_help()

        try:
            if args.cmd == 'call':
                resp = self.__call_service(args.service, additonal_args)
                return {
                    'attachments': [
                        {
                            'text': 'Response:\n```\n%s\n```' % resp,
                            'author_name': args.service
                        }
                    ],
                    'text': '_called `%s`_' % args.service
                }
            elif args.cmd == 'list':
                services = get_service_list()
                return {
                    'attachments': [
                        {
                            'text': (
                                '*Currently available services:*\n```\n%s\n```'
                                % '\n'.join(services)),
                            'author_name': 'ROS master'
                        }
                    ],
                    'text': '_Services:_'
                }
        except Exception as e:
            return '```\n%s\n```' % str(e)

    def on_slash(self, service, payload):
        args = payload['text'].split(' ')

        if service == 'rostopic':
            return self._rostopic(args)
        elif service == 'rosservice':
            return self._rosservice(args)
        else:
            args[0] = self.ROS_PREFIX + '/' + service
            return self._rosservice(args)

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
    print topics
    url_prefix = rospy.get_param(
        '~url_prefix', '')
    sc = RosConnector(
        incoming_webhook=hook,
        whitelist_users=wl_users.split(' '),
        whitelist_channels=wl_channels.split(' '),
        topics=topics.split(' '),
        prefix=url_prefix
    )
    sc.run()
