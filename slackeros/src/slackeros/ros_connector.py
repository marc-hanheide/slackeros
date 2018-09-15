import web

from pprint import pformat
from os import _exit
import signal
from base_connector import SlackConnector
import rospy
from std_msgs.msg import String


def __signal_handler(signum, frame):
    print "stopped."
    _exit(signal.SIGTERM)


class RosConnector(SlackConnector):
    def __init__(
        self,
        incoming_webhook=None,
        whitelist_channels=[],
        whitelist_users=[],
        topics=['~to_slack'],
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
        self.slash_subs = {}
        for t in self.topics:
            self.slash_subs[t] = rospy.Subscriber(
                t, String, self.to_slack_cb, callback_args=t)
            #print self.slash_subs[t].__dict__

    def to_slack_cb(self, msg, topic):
        rospy.loginfo('new message to go to Slack: %s' % msg)
        self.send({
            'text': '_New Information on topic %s_' % topic,
            'attachments': [
                {
                    'text': "```\n%s\n```" % msg,
                    'author_name': topic
                }
            ]
        })

    # def on_slash(self, param, payload):
    #     ret = {
    #         'text': '_default handler called_',
    #         'attachments': [
    #             {
    #                 "title": "Synopsis",
    #                 "text": "```\n%s\n```" % pformat(payload)
    #             }
    #         ]
    #     }
    #     self.send('incoming!')
    #     logging.info('on_slash(%s, %s)', param, pformat(payload))
    #     return ret

    # def run(self):
    #     web.application.run(self)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, __signal_handler)
    rospy.init_node('slack_ros')
    sc = RosConnector(
        incoming_webhook='https://hooks.slack.com/services/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',
        whitelist_users=['mhanheide']
    )
    sc.run()
