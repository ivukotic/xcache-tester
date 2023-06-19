# every 5 min tries to access one of the test files through each xcache server sending heartbeats

# status:
# xcache_open => xopen_
# xcahe_read => xread_

# import rucio.client.didclient as dc
import rucio.client.replicaclient as rc
from rucio.client import Client
import sys
import datetime
import time
# from alerts import alarms
from elasticsearch import Elasticsearch, helpers, exceptions as es_exceptions
import json
import requests
from multiprocessing import Process, Queue
from XRootD import client

nproc = 5
procs = []
results = 0


rucio_client = Client()
rucio_client.ping()

# did_client = dc.DIDClient()
rep_client = rc.ReplicaClient()


def addStatus(doc, step, status):
    doc[step+'ok'] = status.ok
    doc[step+'error'] = status.error
    doc[step+'fatal'] = status.fatal
    doc[step+'message'] = status.message
    doc[step+'status'] = status.status
    doc[step+'code'] = status.code


def stater(i, q, r):
    while True:
        if q.empty():
            time.sleep(1)
            continue
        doc = q.get()
        if doc is None:
            q.put(None)
            break
        # print(f'thr:{i}, checking {doc}')
        c = 'root://' + doc['server']
        op = doc['fp']
        o = op[:op.index('//', 10)]  # or 11?
        p = op[op.index('//', 10):]

        # opening and reading through xcache
        try:
            with client.File() as f:
                print(f'thr:{i}, {c}//{op}')
                xostatus, nothing = f.open(c+'//'+o+p, timeout=5)
                print(f'thr:{i} xopen: {xostatus}')
                addStatus(doc, 'xopen_', xostatus)
                if xostatus.ok:
                    xrstatus, data = f.read(offset=0, size=1024, timeout=10)
                    print(f'thr:{i} xread: {xrstatus}')
                    addStatus(doc, 'xread_', xrstatus)
        except Exception as e:
            print('issue reading file from xcache.', e)

        r.put(doc, block=True, timeout=0.1)

    print(f'thr:{i} done.')


def checkOrigin(fp):

    o = fp[:fp.index('//', 10)]
    p = fp[fp.index('//', 10):]

    # stating origin

    try:
        myclient = client.FileSystem(o)
        status, statInfo = myclient.stat(p, timeout=5)
        print(f'origin stat:{status}')  # , statInfo)
    except Exception as e:
        print('issue stating file.', e)
        return False

    if not status.ok:
        return False

    # opening and reading from origin

    try:
        with client.File() as f:
            print("origin opening:", fp)
            ostatus, nothing = f.open(fp, timeout=5)
            print(f'origin open: {ostatus}')
            if ostatus.ok:
                rstatus, data = f.read(offset=0, size=1024, timeout=10)
                print(f'origin read: {rstatus}')
    except Exception as e:
        print('issue reading file from origin.', e)
        return False

    if not ostatus.ok or not rstatus.ok:
        return False

    return True


def simple_store(r):
    print("storring results.")
    allDocs = []
    while not r.empty():
        doc = r.get()
        doc['_index'] = "remote_io_retries"
        doc['timestamp'] = int(time.time()*1000)
        allDocs.append(doc)
    print('received results:', len(allDocs))

    try:
        print('storing results in ES.')
        res = helpers.bulk(es, allDocs, raise_on_exception=True)
        print("inserted:", res[0], '\tErrors:', res[1])
    except es_exceptions.ConnectionError as e:
        print('ConnectionError ', e)
    except es_exceptions.TransportError as e:
        print('TransportError ', e)
    except helpers.BulkIndexError as e:
        print(e[0])
        for i in e[1]:
            print(i)
    except Exception as e:
        print('Something seriously wrong happened.', e)
    print('done storing.')


def get_active_xcaches():
    res = requests.get('https://vps.cern.ch/liveness')
    jdoc = res.json()
    toTest = []
    for site in jdoc.values():
        servers = site.values()
        for server in servers:
            # print(server)
            if server['address'].startswith('10.'):
                print('internal. skip.')
                continue
            if server['address'] == '163.1.5.200':
                print('OX non VP. skip.')
                continue
            toTest.append(server)
    return toTest


if __name__ == "__main__":

    with open('/config/config.json') as json_data:
        config = json.load(json_data,)

    es = Elasticsearch(
        hosts=[{'host': config['ES_HOST'], 'port':9200, 'scheme':'https'}],
        basic_auth=(config['ES_USER'], config['ES_PASS']))
    es.options(request_timeout=60)

    if es.ping():
        print('connected to ES.')
    else:
        print('no connection to ES.')
        sys.exit(1)

    cd = datetime.datetime.utcnow().strftime('%Y-%m-%d')

    q = Queue()  # a queue for files to retry
    r = Queue()  # a queue for results

    # creates processes that will do transfers
    for i in range(nproc):
        p = Process(target=stater, args=(i, q, r))
        p.start()
        procs.append(p)

    for fi in range(1, 288):

        servers = get_active_xcaches()

        scope = 'user.ivukotic'
        name = 'xcache_' + cd + '_' + str(fi)+'.dat'
        print('reading file:', scope, name)

        fps = list(rep_client.list_replicas(dids=[{'scope': scope, 'name': name}]))
        fp = list(fps[0]['pfns'].keys())[0]

        origin_readable = checkOrigin(fp)

        if origin_readable:
            for server in servers:
                q.put({
                    'site': server['site'],
                    'server_id': server['id'],
                    'server': server['address'],
                    'fp': fp
                })

        time.sleep(300)
        simple_store(r)

    q.put(None)

    # waits for the queue to be fully processed (up to 10 min.)
    for i in range(nproc):
        procs[i].join(600)

    simple_store(r)

    print("Done testing.")

# if len(tkids) > 0:
#     ALARM = alarms('Analytics', 'Frontier', 'Bad SQL queries')
#     ALARM.addAlarm(
#         body='Bad SQL queries',
#         source={'users': list(users), 'tkids': list(tkids)}
#     )
