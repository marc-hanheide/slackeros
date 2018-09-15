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

def __signal_handler(signum, frame):
    print "stopped."
    _exit(signal.SIGTERM)


class RosConnector(SlackConnector):
    def __init__(
        self,
        incoming_webhook=None,
        whitelist_channels=[],
        whitelist_users=[],
        topics=['/slackeros/to_slack'],
        prefix=''
    ):
        class DynSub(Thread):

            def __init__(self, topic, cb):
                Thread.__init__(self)
                self.topic = topic
                self.cb = cb

            def run(self):
                rospy.loginfo(
                    'trying to connect to topic %s' %
                    self.topic)
                msg_class, real_topic, _ = get_topic_class(
                    self.topic, blocking=True)
                rospy.Subscriber(
                    real_topic, msg_class, self.cb,
                    callback_args=(self.topic))
                rospy.loginfo(
                    'connected to topic %s' %
                    self.topic)

        self.incoming_webhook = incoming_webhook
        self.whitelist_channels = set(whitelist_channels)
        self.whitelist_users = set(whitelist_users)
        self.topics = set(topics)

        SlackConnector.__init__(
            self, incoming_webhook,
            whitelist_channels, whitelist_users, prefix)

        self.slash_pub = rospy.Publisher('~slash_cmd', String, queue_size=1)
        for t in self.topics:
            DynSub(t, self.to_slack_cb).start()
            #print self.slash_subs[t].__dict__

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

    def on_slash(self, param, payload):
        service = payload['text']
        ret = {
            'text': 'ROS service to be called: %s' % service
            # 'attachments': [
            #     {
            #         "title": "Synopsis",
            #         "text": "```\n%s\n```" % pformat(payload)
            #     }
            # ]
        }
        srv_class = get_service_class_by_name(service)
        proxy = rospy.ServiceProxy(service, srv_class)
        try:
            ret = "```\n%s\n```" % strify_message(proxy.call())
        except Exception as e:
            ret = '*Failed with exception: %s*' % str(e)
        return ret

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
