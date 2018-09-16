import rospy
from std_msgs.msg import String
from rostopic import get_topic_class
from rosservice import get_service_class_by_name
from threading import Thread
from slackeros.srv import SlashCommand
from slackeros.ros_connector import RosConnector


class StdRosServices():
    def __init__(
        self
    ):
        self.srv_call = rospy.Service(
            'slackeros/service',
            SlashCommand,
            self.cb_service)

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
        ret = {}
        try:
            srv_class = get_service_class_by_name(service)
            proxy = rospy.ServiceProxy(service, srv_class)
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
