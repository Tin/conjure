from .exceptions import ConnectionError
from urlparse import parse_qs
from pymongo import MongoClient
from pymongo.uri_parser import parse_uri

_connections = {}


def _get_connection(hosts, max_pool_size=30):
    global _connections

    hosts = ['%s:%d' % host for host in hosts]
    key = ','.join(hosts)
    connection = _connections.get(key)

    if connection is None:
        try:
            connection = _connections[key] = MongoClient(hosts, max_pool_size=max_pool_size)
        except Exception as e:
            raise ConnectionError(e.message)

    return connection


# New pymongo doesn't allow change the setting from URI, let's workaround it
def _filter_out_max_pool_size(uri):
    max_pool_size = 30
    original_uri = uri

    try:
        if '?' in uri:
            uri, options = uri.split('?', 1)
            options = parse_qs(options)
            if 'maxPoolSize' in options:
                max_pool_size = int(options.pop('maxPoolSize')[0])
            options = "&".join(["%s=%s" % (k, v[0]) for k, v in options.iteritems()])
            uri = "%s?%s" % (uri, options)
    except Exception:
        return max_pool_size, original_uri

    return max_pool_size, uri


def connect(uri):
    max_pool_size, uri = _filter_out_max_pool_size(uri)

    parsed_uri = parse_uri(uri, MongoClient.PORT)

    hosts = parsed_uri['nodelist']
    username = parsed_uri['username']
    password = parsed_uri['password']
    database = parsed_uri['database']

    if 'options' in parsed_uri and 'maxPoolSize' in parsed_uri['options']:
        max_pool_size = parsed_uri['options']['maxPoolSize']
        print '%r' % max_pool_size
        del parsed_uri['options']['maxPoolSize']

    db = _get_connection(hosts, max_pool_size)[database]

    if username and password:
        db.authenticate(username, password)

    return db
