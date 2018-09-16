# slackeros

Slack-ROS Connector for Slash commands and incoming webhooks
* see https://api.slack.com/incoming-webhooks
* see https://api.slack.com/slash-commands

configure at https://api.slack.com/apps/
* slash webhook for `/rostopic` should be https://THISERVER:THISPORT/[PREFIX/]slash/rostopic
* slash webhook for `/rosservice` should be https://THISERVER:THISPORT/[PREFIX/]slash/rosservice
* incoming webhook needs to be enabled and given here as argument

Use ngrok to expose local port

## Launch
launch, e.g., as 

```
SLACK_WEBHOOK="https://hooks.slack.com/services/XXX/XXX/XXX" roslaunch slackeros slackeros.launch users:="mhanheide"
```

obviously, add you own webhook
