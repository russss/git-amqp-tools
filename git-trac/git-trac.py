from amqplib import client_0_8 as amqp
from optparse import OptionParser
from ConfigParser import ConfigParser
from collections import defaultdict
import psycopg2
import re, json

BRANCH_TICKET_REGEX = r"ticket-([0-9]+)"
COMMIT_TICKET_REGEX = r"\[?ticket[ :\-#]+([0-9]+)\]?"

parser = OptionParser()
parser.add_option("-f", "--config", dest="config", help="Config File", default="git-trac.cfg")
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

qname, _, _ = channel.queue_declare('git-trac.%s.%s' % (config.get('amqp', 'exchange'),
                                        config.get('amqp', 'key')),
                                        durable=True)
channel.queue_bind(qname, config.get('amqp', 'exchange'), routing_key=config.get('amqp', 'key'))

db = None

def connect_db():
    global db
    if db is None:
        db = psycopg2.connect(database=config.get('db', 'db'), user=config.get('db', 'user'),
                            password=config.get('db', 'password'), host=config.get('db', 'host'),
                            port=config.get('db', 'port'))
    return db

def commit_to_text(repo, commit):
    return "%s@%s: %s" % (repo, commit['sha'][0:7],
                re.sub(COMMIT_TICKET_REGEX, '', commit['message']).split("\n")[0])

def add_comment(ticket_id, repo, branch, commits):
    db = connect_db()
    curs = db.cursor()
    curs.execute("SELECT id FROM ticket WHERE id = %s", (ticket_id,))
    if curs.rowcount == 0:
        return
    string = "Git commits on branch %s:" % branch.split('/')[-1]
    for commit in commits:
        string += "\n * " + commit_to_text(repo, commit)
    curs.execute("""INSERT INTO ticket_change (ticket, time, author, field, oldvalue, newvalue)
                VALUES (%s, %s, 'git', 'comment',
                    COALESCE((SELECT max(oldvalue::integer) FROM ticket_change WHERE ticket = %s
                    AND field = 'comment'), 0) + 1, %s)""",
                    (ticket_id, max(commit['date'] for commit in commits) * 1000000, ticket_id, string))
    db.commit()


def extract_ticket_number(branch, message):
    """
    Extracts the ticket number from the branch or, failing that, the
    commit message.
    """
    match = re.search(BRANCH_TICKET_REGEX, branch, re.I | re.M)
    if match is None:
        match = re.search(COMMIT_TICKET_REGEX, message, re.I | re.M)
    if match is not None:
        return match.group(1)
    return None


def process_message(msg):
    data = json.loads(msg.body)
    for branch, commits in data.items():
        ticket_commits = defaultdict(list)
        for commit in commits:
            ticket_number = extract_ticket_number(branch, commit['message'])
            if ticket_number is not None:
                ticket_commits[ticket_number].append(commit)
        for ticket_id, commits in ticket_commits.items():
            add_comment(ticket_id, msg.delivery_info['routing_key'], branch, commits)

msg = channel.basic_get(qname)
while msg is not None:
    process_message(msg)
    channel.basic_ack(msg.delivery_tag)
    msg = channel.basic_get(qname)
