#!/usr/bin/env python
from flask import Flask, request
from unimate import Client
import json

app = Flask(__name__)

@app.route("/", methods=['POST'])
def callback():
    callback_data = json.loads(request.data)
    text = "[git] push to %s (%s)" % (callback_data['repository']['name'], callback_data['ref'])
    for commit in callback_data['commits']:
        text = text + "\n%s - %s (%s)" % (commit['message'].split("\n")[0],
                                            commit['author']['name'], commit['url'])
    unimate = Client('10.1.0.40', 12344)
    unimate.send(text, room="staff")
    return ""

if __name__ == "__main__":
    app.run(host='0.0.0.0')
