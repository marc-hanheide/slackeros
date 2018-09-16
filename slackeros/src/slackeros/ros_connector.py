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
from threading import Thread
from roslib.message import strify_message
from slackeros.srv import SlashCommand
import argparse
from StringIO import StringIO


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
        help_string = '`usage: /rostopic [subscribe|unsubscribe|list] <topic>`'
        if len(args) < 1:
            return help_string
        else:
            cmd = args[0].lower()
            if cmd == 'subscribe':
                topic = args[1]
                self._subscribe(topic)
                return 'subscribing to `%s`' % topic
            elif cmd == 'unsubscribe':
                topic = args[1]
                self._unsubscribe(topic)
                return 'unsubscribing from `%s`' % topic
            elif cmd == 'list':
                topics = rospy.get_published_topics()
                tops = [('%s [%s]' % (t[0], t[1])) for t in topics]
                print tops
                return {
                    'attachments': [
                        {
                            'text': '```\n%s\n```' % '\n'.join(tops),
                            'author_name': 'ROS master:'
                        }
                    ],
                    'text': 'Currently published topics:'
                }
            else:
                return help_string

    def on_slash(self, service, payload):
        args = payload['text'].split(' ')

        if service == 'rostopic':
            return self._rostopic(args)
        elif service == 'rosservice':
            return self._rosservice(args)
        else:
            return '_unknown command `%s`' % service
        #     ret = {}
        #     try:
        #         srv_class = get_service_class_by_name(service)
        #         proxy = rospy.ServiceProxy(service, srv_class)
        #         ret = "```\n%s\n```" % strify_message(proxy.call())
        #     except Exception as e:
        #         ret = '*Failed with exception: %s*' % str(e)
        # return ret

    # def run(self):
    #     web.application.run(self)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, __signal_handler)
    rospy.init_node('slackeros')
    sc = RosConnector(
        incoming_webhook='https://hooks.slack.com/services/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',
        whitelist_users=['mhanheide']
    )
    sc.run()
