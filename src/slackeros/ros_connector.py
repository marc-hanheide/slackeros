import os
import signal
from base_connector import SlackConnector
import rospy
from std_msgs.msg import String
from rostopic import get_topic_class
from rosservice import get_service_class_by_name
from rosservice import get_service_list
from threading import Thread
from roslib.message import strify_message
import argparse
import roslib
import rosmsg
from collections import defaultdict
from datetime import datetime
from Queue import Queue, Empty

import cv2
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError

def __signal_handler(signum, frame):
    print "stopped."
    _exit(signal.SIGTERM)


class RosConnector(SlackConnector):

    ROS_PREFIX = '/slackeros'
    LEVEL_SETS = {
        'info': set([2, 4, 8, 16]),
        'warn': set([4, 8, 16]),
        'warning': set([4, 8, 16]),
        'error': set([8, 16]),
        'fatal': set([16]),
        'off': set([])
    }
    REVERSE_LEVEL_SET = {
        0: 'off',
        1: 'debug',
        2: 'info',
        4: 'warn',
        8: 'error',
        16: 'fatal'
    }
    LEVEL_COLORS = {
        0: '#000000',
        1: '#CCCCCC',
        2: '#888888',
        4: '#FF8C00',
        8: '#FF0000',
        16: '#FF0000'
    }

    def __init__(
        self,
        incoming_webhook=None,
        access_token=None,
        upload_images=False,
        whitelist_channels=[],
        whitelist_users=[],
        topics=[ROS_PREFIX + '/to_slack'],
        prefix='',
        loggers={},
        throttle_secs=5,
        max_lines=50
    ):
        self.incoming_webhook = incoming_webhook
        self.access_token = access_token
        self.upload_images = upload_images
        self.whitelist_channels = set(whitelist_channels)
        self.whitelist_users = set(whitelist_users)
        self.topics = set(topics)
        self.max_lines = max_lines
        self.messages = Queue(0)
        self.last_published = defaultdict(rospy.Time)
        self.throttle_secs = throttle_secs

	self.bridge = CvBridge()
        SlackConnector.__init__(
            self, incoming_webhook,
            whitelist_channels, whitelist_users, prefix)

        self.slash_pub = rospy.Publisher('~slash_cmd', String, queue_size=1)
        self.subs = {}

        for t in self.topics:
            self._subscribe(t)

        self.default_level = 'off'
        self.attachment_buffer = defaultdict(list)
        self.message_header = defaultdict(lambda: 'new data')
        self.active_loggers = defaultdict(lambda: self.default_level)
        if loggers:
            self.logger_enabled = True
            self.active_loggers.update(loggers)
            self._subscribe('/rosout', self._log_received)
        else:
            self.logger_enabled = False
        self.last_attachment = defaultdict(lambda: '')

        self.queue_worker = Thread(target=self.process_queue)
        self.queue_worker.setDaemon(True)
        self.queue_worker.start()

    def log_image(self, type=None, topic='/head_xtion/rgb/image_color'):
        class ImageUploader(Thread):

            def __init__(self, access_token, bridge, send_image, type=None, image_format='jpeg', whitelist_channels=[], image_upload_title="", topic='/head_xtion/rgb/image_color'):
                Thread.__init__(self)
                self.access_token = access_token
                self.bridge = bridge
                self.send_image = send_image
                self.type = type
                self.image_format = image_format
                self.whitelist_channels = whitelist_channels
                self.image_upload_title = image_upload_title
                self.topic = topic

            def run(self):
                # upload image
                try:
                    image = rospy.wait_for_message(self.topic, Image, timeout=1.5)
                except rospy.ROSException as e:
                    rospy.logwarn("No image retrieved before timeout")
                    return

                if self.type is None:
                    self.type = image.encoding
                try:
                    # Convert your ROS Image message to OpenCV2
                    if self.type == "rgb8": self.type = "bgr8"
                    cv2_img = self.bridge.imgmsg_to_cv2(image, self.type)
                except CvBridgeError, e:
                    rospy.logwarn(e)
                else:
                    # Save your OpenCV2 image as a jpeg
                    image_file = '/tmp/camera_image.jpeg'
                    cv2.imwrite(image_file, cv2_img)
                    # upload to slack
                    params = {
                    'token': self.access_token,
                    'channels': '#administration',
                    'filename': image_file,
                    'filetype': 'jpeg',
                    'title': 'Image from the robot camera'
                    }
                    file = {
                        'file': open(image_file, 'rb')
                    }
                    self.send_image(params, file)
                    rospy.loginfo("Image %s uploaded to slack with encoding %s" % (image_file, self.type))

        ImageUploader(self.access_token, self.bridge, self.send_image, type, self.image_format, self.whitelist_channels, self.image_upload_title, topic).start()

    def process_queue(self):

        def __send_out(t):
            if self.attachment_buffer[t]:
                m = {
                    'text': self.message_header[t],
                    'attachments': self.attachment_buffer[t]
                }
                rospy.logdebug('sending out: %s' % str(m))
                self.send(m)
                self.attachment_buffer[t] = []
		if self.upload_images:
                    self.log_image(type="rgb8")

        while not rospy.is_shutdown():
            try:
                (topic, attachment) = self.messages.get(
                    True, timeout=self.throttle_secs)
                self.attachment_buffer[topic].append(attachment)

                time_elapsed = rospy.Time.now() - self.last_published[topic]
                if time_elapsed.to_sec() > self.throttle_secs:
                    self.last_published[topic] = rospy.Time.now()
                    __send_out(topic)

                self.messages.task_done()
            except Empty:
                rospy.logdebug('wait time up, time to flush all')
                for t in self.attachment_buffer:
                    __send_out(t)

    def _subscribe(self, topic, cb=None):
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

        if cb is None:
            cb = self._to_slack_cb
        DynSub(topic, cb, __connected).start()

    def _unsubscribe(self, topic):
        if topic in self.subs:
            self.subs[topic].unregister()
            del self.subs[topic]

    def _poll(self, topic, timeout=1.5):
        msg_class, real_topic, _ = get_topic_class(
            topic, blocking=False)
        if msg_class is None:
            return '`topic %s not found`' % topic
        elif msg_class == Image:
            self.log_image(topic=topic)
            return 'uploading image...'
        try:
            msg = rospy.wait_for_message(
                topic, msg_class, timeout)
            return self.__generate_output(msg)
        except Exception as e:
            return (
                'no message received after %.1f seconds: %s' % (
                    timeout,
                    str(e)
                    )
                )

    def __generate_output(self, msg):
        d = strify_message(msg)
        # truncate message
        lines = d.splitlines()
        if len(lines) > self.max_lines:
            rospy.loginfo(
                'output truncated, too long (shown %d of %d lines only).' %
                (self.max_lines, len(lines)))
            d = '\n'.join(lines[0:self.max_lines])
            d += (
                '\n\n[%s]' %
                '*** output truncated, too long '
                '(showing %d of %d lines only). ***' %
                (self.max_lines, len(lines))
            )
        return d

    def _push(self, topic, attachment):
        self.messages.put((topic, attachment,))

    def _to_slack_cb(self, msg, topic):

        rospy.logdebug('msg received on topic %s' % topic)
        d = self.__generate_output(msg)
        att = {
                'text': "```\n%s\n```" % d,
                "mrkdwn_in": ["text", "pretext"],
                'pretext': (
                    'published by node `%s` on `%s`' %
                    (msg._connection_header['callerid'], topic)),
                'footer': '%s' % str(datetime.now()),
                "fallback": d,
                "color": '#0000AA',
                'ts': rospy.Time.now().secs
            }
        self.message_header[topic] = (
            '_new message(s) on : `%s`_' %
            topic
            )

        self._push(topic, att)

    def _log_received(self, log_entry, topic):
        # make sure we are not listening to ourselves
        if log_entry.name == rospy.get_name():
            return

        level = log_entry.level
        logger = log_entry.name

        if level not in RosConnector.LEVEL_SETS[
               self.active_loggers[logger]
               ]:
            return

        att = {
            'text': (
                '> %s\n'
                '_level:_ `%s`\n'
                '_file:_ `%s`\n'
                '_function:_ `%s`\n'
                '_line:_ `%s`\n' %
                (
                    log_entry.msg,
                    RosConnector.REVERSE_LEVEL_SET[
                        log_entry.level],
                    log_entry.file,
                    log_entry.function,
                    log_entry.line
                    )
                ),
            "mrkdwn_in": ["text", "pretext"],
            "fallback": str(log_entry),
            "pretext": "*%s*" % RosConnector.REVERSE_LEVEL_SET[
                        log_entry.level],
            "color": self.LEVEL_COLORS[level],
            'author_name': '/rosout from "%s"' % logger,
            'footer': '%s' % str(datetime.utcfromtimestamp(
                        log_entry.header.stamp.secs)),
            'ts': log_entry.header.stamp.secs
            }

        self.message_header['__logger__' + logger] = (
            '*Logging Event* from node: `%s`' %
            logger
            )
        self._push('__logger__' + logger, att)

    def _roslogger(self, args):
        parser = argparse.ArgumentParser(prog='/roslogger')
        subparsers = parser.add_subparsers(dest='cmd',
                                           help='sub-command')
        subparsers.add_parser('enable', help='enable logging')
        subparsers.add_parser('disable', help='disable logging')
        subparsers.add_parser('list', help='show loggers')
        parser_set = subparsers.add_parser(
            'set', help='set level node: /roslogger set <nodename> {%s}' %
            '|'. join(RosConnector.LEVEL_SETS.keys())
            )
        parser_set.add_argument(
            'logger', help='logger to set'
            )
        parser_set.add_argument(
            'level', help='level to set logger to',
            choices=RosConnector.LEVEL_SETS.keys()
            )
        subparsers.add_parser(
            'setall', help='set level for nodes: /roslogger setall  {%s}' %
            '|'. join(RosConnector.LEVEL_SETS.keys())
        ).add_argument(
            'level', help='level to set logger to',
            choices=RosConnector.LEVEL_SETS.keys()
            )

        try:
            args = parser.parse_args(args)
        except SystemExit:
            return '```\n%s\n```' % parser.format_help()

        if args.cmd == 'enable':
            self._subscribe('/rosout', self._log_received)
            self.logger_enabled = True
            return 'subscribing to `/rosout`'
        elif args.cmd == 'disable':
            self._unsubscribe('/rosout')
            self.logger_enabled = False
            return 'unsubscribing from `/rosout`'
        elif args.cmd == 'set':
            self.active_loggers[args.logger] = args.level.lower()
            return 'logger `%s` set to level `%s`' % (
                args.logger,
                args.level
                )
        elif args.cmd == 'setall':
            self.default_level = args.level.lower()
            for l in self.active_loggers:
                self.active_loggers[l] = self.default_level
            return 'all loggers set to level `%s`' % (
                args.level
                )
        elif args.cmd == 'list':
            loggers = [
                ('%s [%s]' % (l, self.active_loggers[l]))
                for l in self.active_loggers]
            return {
                'attachments': [
                    {
                        'text': (
                            '*configured loggers:*\n```\n%s\n```'
                            % '\n'.join(loggers)),
                        'author_name': 'slackerros'
                    }
                ],
                'text': (
                    '_logging enabled_'
                    if self.logger_enabled else '~logging disabled~'
                    )
            }


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
        subparsers.add_parser(
            'poll', help='poll one value from topic: /rostopic read <topic>'
            ).add_argument(
            'topic', help='topic to read from to'
            )

        try:
            args = parser.parse_args(args)
        except SystemExit:
            return '```\n%s\n```' % parser.format_help()

        if args.cmd == 'subscribe':
            self._subscribe(args.topic)
            return 'subscribing to `%s`' % args.topic
        elif args.cmd == 'unsubscribe':
            self._unsubscribe(args.topic)
            return 'unsubscribing from `%s`' % args.topic
        elif args.cmd == 'poll':
            return '```\n%s\n```' % self._poll(args.topic)
        elif args.cmd == 'list':
            topics = rospy.get_published_topics()
            tops = [('%s [%s]' % (t[0], t[1])) for t in topics]
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
        elif service == 'roslogger':
            return self._roslogger(args)
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
    token = rospy.get_param(
        '~access_token',
        'xoxb-xxxxxxxxxxxxx-xxxxxxxxxxxxxxxxx-xxxxxxxxxxxxxxx')
    wl_users = rospy.get_param(
        '~users', '')
    wl_channels = rospy.get_param(
        '~channels', '')
    topics = rospy.get_param(
        '~topics', '')
    url_prefix = rospy.get_param(
        '~url_prefix', '')
    sc = RosConnector(
        incoming_webhook=hook,
        access_token=token,
        whitelist_users=wl_users.split(' '),
        whitelist_channels=wl_channels.split(' '),
        topics=topics.split(' '),
        prefix=url_prefix
    )
    sc.run()
