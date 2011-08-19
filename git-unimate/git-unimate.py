from amqplib import client_0_8 as amqp
from optparse import OptionParser
from ConfigParser import ConfigParser
from collections import defaultdict
from unimate import Client as UnimateClient
import re, json

parser = OptionParser()
parser.add_option("-f", "--config", dest="config", help="Config File", default="git-unimate.cfg")
(options, args) = parser.parse_args()

config = ConfigParser()
config.read(options.config)

conn = amqp.Connection(host=config.get('amqp', 'host'), port=config.get('amqp', 'port'),
                        userid=config.get('amqp', 'user'),
                        password=config.get('amqp', 'password'),
                        virtual_host=config.get('amqp', 'vhost'))
channel = conn.channel()
channel.access_request('/data', active=True, read=True)
channel.exchange_declare(config.get('amqp', 'exchange'), type='topic', durable=True, auto_delete=False)

qname, _, _ = channel.queue_declare('git-unimate.%s.%s' % (config.get('amqp', 'exchange'),
                                        config.get('amqp', 'key')))
channel.queue_bind(qname, config.get('amqp', 'exchange'), routing_key=config.get('amqp', 'key'))

unimate = UnimateClient(config.get('unimate', 'host'), config.getint('unimate', 'port'))

def get_url(repo, commit):
    return "http://git.corp.smarkets.com/?p=%s;a=commitdiff;h=%s" % (repo, commit['sha'][0:7])

def report_commits(repository, branch, commits):
    text = "Push to %s:%s:" % (repository, branch)
    for commit in commits:
        text = text + "\n%s - %s (%s)" % (commit['message'].split("\n")[0],
                                commit['author']['name'], get_url(repository, commit))
    unimate.send(text, room="staff")

def process_message(msg):
    data = json.loads(msg.body)
    for branch, commits in data.items():
        report_commits(msg.delivery_info['routing_key'], branch, commits)

channel.basic_consume(queue=qname, no_ack=True, callback=process_message)

while True:
    channel.wait()
