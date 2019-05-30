#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2019, Dmitriy Kaminskiy <dmitriy@kaminskiy.pro>
# (c) 2017, Steve Pletcher <steve@steve-pletcher.com>
# (c) 2016, René Moser <mail@renemoser.net>
# (c) 2015, Stefan Berggren <nsg@nsg.cc>
# (c) 2014, Ramon de la Fuente <ramon@delafuente.nl>
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '0.1',
                    'status': ['local'],
                    'supported_by': 'community'}


DOCUMENTATION = """
module: slack_webapi
short_description: Send Slack notifications via the Slack Web API
description:
    - The C(slack_webapi) module sends notifications to U(http://slack.com) via the Slack Web API interface
      Module based on slack module by Ramon de la Fuente (@ramondelafuente), but uses the Slack Web API
      instead of the Incoming WebHook integration. Main goals is to get proper JSON responce from Slack server
      and use 'chat.update' Slack API method.
version_added: "2.8"
author: "Dmitriy Kaminskiy ( dmitriy@kaminskiy.pro )"
options:
  token:
    description:
      - Slack OAuth Access Token. This authenticates your app to the slack service.
        Tokens look like C(xoxp-00000000000-00000000000-000000000000-00000aa0a00a0a0a0aa0aaf00b00a00d).
    required: true
  method:
    description:
      - Slack API Method (https://api.slack.com/methods). 'chat.postMessage' and 'chat.update' supports for now.
        If absent, the 'chat.postMessage' will be used.
    default: 'chat.postMessage'
  msg:
    description:
      - Message to send. Note that the module does not handle escaping characters.
        Plain-text angle brackets and ampersands should be converted to HTML entities (e.g. & to &amp;) before sending.
        See Slack's documentation (U(https://api.slack.com/docs/message-formatting)) for more.
  channel:
    description:
      - Channel to send the message to. If absent, the message goes to the channel selected for the I(token).
        In case "chat.postMessage" (https://api.slack.com/methods/chat.postMessage) methot can be an encoded ID, or a name.
        In case "chat.update" (https://api.slack.com/methods/chat.update) method channel ID supports only.
  thread_id:
    description:
      - Optional. Timestamp of message to thread this message to as a float. https://api.slack.com/docs/message-threading
  username:
    description:
      - This is the sender of the message.
    default: "Ansible"
  icon_url:
    description:
      - Url for the message sender's icon (default C(https://www.ansible.com/favicon.ico))
  icon_emoji:
    description:
      - Emoji for the message sender. See Slack documentation for options.
        (if I(icon_emoji) is set, I(icon_url) will not be used)
  link_names:
    description:
      - Automatically create links for channels and usernames in I(msg).
    default: 1
    choices:
      - 1
      - 0
  parse:
    description:
      - Setting for the message parser at Slack
    choices:
      - 'full'
      - 'none'
  validate_certs:
    description:
      - If C(no), SSL certificates will not be validated. This should only be used
        on personally controlled sites using self-signed certificates.
    type: bool
    default: 'yes'
  color:
    description:
      - Allow text to use default colors - use the default of 'normal' to not send a custom color bar at the start of the message.
      - Allowed values for color can be one of 'normal', 'good', 'warning', 'danger', any valid 3 digit or 6 digit hex color value.
      - Specifying value in hex is supported from version 2.8.
    default: 'normal'
  attachments:
    description:
      - Define a list of attachments. This list mirrors the Slack JSON API.
      - For more information, see also in the (U(https://api.slack.com/docs/attachments)).
"""

EXAMPLES = """
- name: Send notification message via Slack
  slack:
    token: the-token-generated-by-slack
    msg: '{{ inventory_hostname }} completed'
  delegate_to: localhost

- name: Send notification message via Slack all options
  slack:
    token: the-token-generated-by-slack
    msg: '{{ inventory_hostname }} completed'
    channel: '#ansible'
    thread_id: 1539917263.000100
    username: 'Ansible on {{ inventory_hostname }}'
    icon_url: http://www.example.com/some-image-file.png
    link_names: 0
    parse: 'none'
  delegate_to: localhost

- name: insert a color bar in front of the message for visibility purposes and use the default webhook icon and name configured in Slack
  slack:
    token: the-token-generated-by-slack
    msg: '{{ inventory_hostname }} is alive!'
    color: good
    username: ''
    icon_url: ''

- name: insert a color bar in front of the message with valid hex color value
  slack:
    token: the-token-generated-by-slack
    msg: 'This message uses color in hex value'
    color: '#00aacc'
    username: ''
    icon_url: ''

- name: Use the attachments API
  slack:
    token: the-token-generated-by-slack
    attachments:
      - text: Display my system load on host A and B
        color: '#ff00dd'
        title: System load
        fields:
          - title: System A
            value: "load average: 0,74, 0,66, 0,63"
            short: True
          - title: System B
            value: 'load average: 5,16, 4,64, 2,43'
            short: True

- name: Send a message with a link using Slack markup
  slack:
    token: the-token-generated-by-slack
    msg: We sent this message using <https://www.ansible.com|Ansible>!

- name: Send a message with angle brackets and ampersands
  slack:
    token: the-token-generated-by-slack
    msg: This message has &lt;brackets&gt; &amp; ampersands in plain text.
"""

import re
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url
import json


API_POST_MESSAGE = 'https://slack.com/api/'

# Escaping quotes and apostrophes to avoid ending string prematurely in ansible call.
# We do not escape other characters used as Slack metacharacters (e.g. &, <, >).
escape_table = {
    '"': "\"",
    "'": "\'",
}


def is_valid_hex_color(color_choice):
    if re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', color_choice):
        return True
    return False


def escape_quotes(text):
    '''Backslash any quotes within text.'''
    return "".join(escape_table.get(c, c) for c in text)


def build_payload_for_slack(module, text, channel, thread_id, username, icon_url, icon_emoji, link_names,
                            parse, color, attachments):
    payload = {}
    if color == "normal" and text is not None:
        payload = dict(text=escape_quotes(text))
    elif text is not None:
        # With a custom color we have to set the message as attachment, and explicitly turn markdown parsing on for it.
        payload = dict(attachments=[dict(text=escape_quotes(text), color=color, mrkdwn_in=["text"])])
    if channel is not None:
        payload['channel'] = channel
    if thread_id is not None:
        payload['thread_ts'] = thread_id
    if username is not None:
        payload['username'] = username
    if icon_emoji is not None:
        payload['icon_emoji'] = icon_emoji
    else:
        payload['icon_url'] = icon_url
    if link_names is not None:
        payload['link_names'] = link_names
    if parse is not None:
        payload['parse'] = parse

    if attachments is not None:
        if 'attachments' not in payload:
            payload['attachments'] = []

    if attachments is not None:
        keys_to_escape = [
            'title',
            'text',
            'author_name',
            'pretext',
            'fallback',
        ]
        for attachment in attachments:
            for key in keys_to_escape:
                if key in attachment:
                    attachment[key] = escape_quotes(attachment[key])

            if 'fallback' not in attachment:
                attachment['fallback'] = attachment['text']

            payload['attachments'].append(attachment)

    payload = module.jsonify(payload)
    return payload

def build_update_payload_for_slack(module, text, channel, ts, username, icon_url, icon_emoji, link_names,
                            parse, color, attachments):
    payload = {}
    if color == "normal" and text is not None:
        payload = dict(text=escape_quotes(text))
    elif text is not None:
        # With a custom color we have to set the message as attachment, and explicitly turn markdown parsing on for it.
        payload = dict(attachments=[dict(text=escape_quotes(text), color=color, mrkdwn_in=["text"])])
    if channel is not None:
        payload['channel'] = channel
    if ts is not None:
        payload['ts'] = ts
    if username is not None:
        payload['username'] = username
    if icon_emoji is not None:
        payload['icon_emoji'] = icon_emoji
    else:
        payload['icon_url'] = icon_url
    if link_names is not None:
        payload['link_names'] = link_names
    if parse is not None:
        payload['parse'] = parse

    if attachments is not None:
        if 'attachments' not in payload:
            payload['attachments'] = []

    if attachments is not None:
        keys_to_escape = [
            'title',
            'text',
            'author_name',
            'pretext',
            'fallback',
        ]
        for attachment in attachments:
            for key in keys_to_escape:
                if key in attachment:
                    attachment[key] = escape_quotes(attachment[key])

            if 'fallback' not in attachment:
                attachment['fallback'] = attachment['text']

            payload['attachments'].append(attachment)

    payload = module.jsonify(payload)
    return payload



def do_notify_slack(module, method, token, payload):
    api_post_message = API_POST_MESSAGE + str(method)

    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
        'Authorization': 'Bearer %s' % (token),
    }

    response, info = fetch_url(module=module, url=api_post_message, headers=headers, method='POST', data=payload)

    if info['status'] != 200:
        module.fail_json(msg=" failed to send %s to %s: %s" % (payload, api_post_message, info['msg']))

    if response is not None:
        body = json.loads(response.read())

    if info['status'] == 200:
        if str(body.get('ok')) in str("True"):
            module.exit_json(msg="Status ok: %s" % (body['ok']),slackreply=body )
        else:
            module.fail_json(msg="Failed. payload:  %s, slackreply: %s" % (payload, body))

def main():
    module = AnsibleModule(
        argument_spec=dict(
            domain=dict(type='str', required=False, default=None),
            token=dict(type='str', required=True, no_log=True),
            msg=dict(type='str', required=False, default=None),
            channel=dict(type='str', default=None),
            thread_id=dict(type='str', default=None),
            ts=dict(type='str', default=None),
            method=dict(type='str', default='chat.postMessage'),
            username=dict(type='str', default='Ansible'),
            icon_url=dict(type='str', default='https://www.ansible.com/favicon.ico'),
            icon_emoji=dict(type='str', default=None),
            link_names=dict(type='int', default=1, choices=[0, 1]),
            parse=dict(type='str', default=None, choices=['none', 'full']),
            validate_certs=dict(default='yes', type='bool'),
            color=dict(type='str', default='normal'),
            attachments=dict(type='list', required=False, default=None)
        )
    )

    domain = module.params['domain']
    token = module.params['token']
    text = module.params['msg']
    channel = module.params['channel']
    thread_id = module.params['thread_id']
    ts = module.params['thread_id']
    method = module.params['method']
    username = module.params['username']
    icon_url = module.params['icon_url']
    icon_emoji = module.params['icon_emoji']
    link_names = module.params['link_names']
    parse = module.params['parse']
    color = module.params['color']
    attachments = module.params['attachments']

    color_choices = ['normal', 'good', 'warning', 'danger']
    if color not in color_choices and not is_valid_hex_color(color):
        module.fail_json(msg="Color value specified should be either one of %r "
                             "or any valid hex value with length 3 or 6." % color_choices)

    if method == 'chat.postMessage':
        payload = build_payload_for_slack(module, text, channel, thread_id, username, icon_url, icon_emoji, link_names,
                                          parse, color, attachments)
    if method == 'chat.update':
        payload = build_update_payload_for_slack(module, text, channel, ts, username, icon_url, icon_emoji, link_names,
                                          parse, color, attachments)
    do_notify_slack(module, method, token, payload)

    module.exit_json(msg="OK")
#    module.exit_json(msg="OK: %s, ts: %s" % (payload, info['msg']))

if __name__ == '__main__':
    main()
