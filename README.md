# slack-webapi-ansible-module
The `slack_webapi' module sends notifications to http://slack.com via the Slack Web API interface.
It is based on [slack](https://docs.ansible.com/ansible/latest/modules/slack_module.html) Ansible module by Ramon de la Fuente (@ramondelafuente), but uses the Slack Web API instead of the Incoming WebHook integration.

Main goals is to get proper JSON responce from Slack server and use 'chat.update' Slack API method.

The C(slack) module sends notifications to U(http://slack.com) via the Slack Web API interface
      Module based on slack module by Ramon de la Fuente (@ramondelafuente), but uses the Slack Web API
      instead of the Incoming WebHook integration. Main goals are to get proper JSON responce from Slack server
      and use 'chat.update' Slack API method.

## Add a module locally
See here: https://docs.ansible.com/ansible/latest/dev_guide/developing_locally.html#adding-a-module-locally

## How to use
See example.
