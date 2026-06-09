# every 5 min tries to access one of the test files through each xcache server sending heartbeats

# status:
# xcache_open => xopen_
# xcahe_read => xread_

import sys
import subprocess
import datetime
import time
# from alerts import alarms
from elasticsearch import Elasticsearch, helpers, exceptions as es_exceptions
import json
import requests
from multiprocessing import Process, Queue
from XRootD import client

import faulthandler
import signal
faulthandler.register(signal.SIGUSR1.value)

nproc = 5
procs = []
results = 0


def addStatus(doc, step, status):
    doc[step+'ok'] = status.ok
    doc[step+'error'] = status.error
    doc[step+'fatal'] = status.fatal
    doc[step+'message'] = status.message
    doc[step+'status'] = status.status
    doc[step+'code'] = status.code


def expunge(server):
    nfp = '/atlas/rucio/user/ivukotic/7d/9b/xcache.test.dat'
    try:
        cp = subprocess.run(["xrdfs", server, "cache", "fevict", nfp], timeout=30)
        if cp.returncode:
            print('issue cleaning cached file for server:', server)
        return cp.returncode
    except subprocess.TimeoutExpired:
        print(f'expunge timed out for server: {server}', flush=True)
        return 1


def test_server(doc, r):
    # Runs in its own subprocess so all XRootD TCP connections are closed on exit,
    # signalling xcache to close its origin connections.
    c = 'root://' + doc['server']
    op = doc['fp']
    o = op[:op.index('//', 10)]
    p = op[op.index('//', 10):]

    expunge(doc['server'])

    try:
        with client.File() as f:
            print(f'checking {c}//{op}', flush=True)
            xostatus, nothing = f.open(c+'//'+o+p, timeout=5)
            print(f'xopen: {xostatus}', flush=True)
            addStatus(doc, 'xopen_', xostatus)
            if xostatus.ok:
                xrstatus, data = f.read(offset=0, size=1024, timeout=10)
                print(f'xread: {xrstatus}', flush=True)
                addStatus(doc, 'xread_', xrstatus)
    except Exception as e:
        print('issue reading file from xcache.', e, flush=True)

    r.put(doc)


def checkOrigin(fp):

    o = fp[:fp.index('//', 10)]
    p = fp[fp.index('//', 10):]
    print("---", datetime.datetime.now(), "---")
    print("stating origin", flush=True)

    try:
        myclient = client.FileSystem(o)
        status, statInfo = myclient.stat(p, timeout=5)
        print(f'origin stat:{status}', flush=True)  # , statInfo)
    except Exception as e:
        print('issue stating file.', e, flush=True)
        return False

    if not status.ok:
        return False

    print("opening and reading from origin", flush=True)

    try:
        with client.File() as f:
            print("opening:", fp, flush=True)
            ostatus, nothing = f.open(fp, timeout=5)
            print(f'open: {ostatus}', flush=True)
            if ostatus.ok:
                rstatus, data = f.read(offset=0, size=1024, timeout=10)
                print(f'read: {rstatus}', flush=True)
    except Exception as e:
        print('issue reading file from origin.', e, flush=True)
        return False

    if not ostatus.ok or not rstatus.ok:
        return False

    return True


def simple_store(r):
    print("storring results.", flush=True)
    allDocs = []
    while not r.empty():
        doc = r.get()
        doc['_index'] = "remote_io_retries"
        doc['timestamp'] = int(time.time()*1000)
        allDocs.append(doc)
    print('received results:', len(allDocs), flush=True)

    try:
        print('storing results in ES.', flush=True)
        res = helpers.bulk(es, allDocs, raise_on_exception=True)
        print("inserted:", res[0], '\tErrors:', res[1], flush=True)
    except es_exceptions.ConnectionError as e:
        print('ConnectionError ', e, flush=True)
    except es_exceptions.TransportError as e:
        print('TransportError ', e, flush=True)
    except helpers.BulkIndexError as e:
        print(e[0], flush=True)
        for i in e[1]:
            print(i, flush=True)
    except Exception as e:
        print('Something seriously wrong happened.', e, flush=True)
    print('done storing.', flush=True)


def get_active_xcaches():
    res = requests.get('https://vps.cern.ch/liveness', timeout=30)
    jdoc = res.json()
    toTest = []
    for site in jdoc.values():
        servers = site.values()
        for server in servers:
            # print(server)
            if server['address'].startswith('10.'):
                print('internal. skip.', flush=True)
                continue
            # if server['address'] == '163.1.5.200':
            #     print('OX non VP. skip.', flush=True)
            #     continue
            toTest.append(server)
    return toTest


if __name__ == "__main__":

    with open('/config/config.json') as json_data:
        config = json.load(json_data,)

    es = Elasticsearch(
        hosts=[{'host': config['ES_HOST'], 'port': 9200, 'scheme': 'https'}],
        basic_auth=(config['ES_USER'], config['ES_PASS']))
    es.options(request_timeout=60)

    if es.ping():
        print('connected to ES.')
    else:
        print('no connection to ES.')
        sys.exit(1)

    r = Queue()  # a queue for results

    fp = 'root://fax.mwt2.org:1094//pnfs/uchicago.edu/atlaslocalgroupdisk/rucio/user/ivukotic/7d/9b/xcache.test.dat'
    cd = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    print('starting at:', cd)

    servers = get_active_xcaches()

    origin_readable = checkOrigin(fp)

    if not origin_readable:
        print('Test file issue. Quiting after an hour of sleep')
        time.sleep(3600)
        sys.exit(1)

    # Spawn one process per server so XRootD connections are closed on process exit,
    # preventing xcache from keeping stale connections to origin servers.
    for server in servers:
        doc = {
            'site': server['site'],
            'server_id': server['id'],
            'server': server['address'],
            'fp': fp
        }
        p = Process(target=test_server, args=(doc, r), daemon=True)
        p.start()
        procs.append(p)

        # Throttle: keep at most nproc tests running concurrently
        while sum(1 for proc in procs if proc.is_alive()) >= nproc:
            time.sleep(1)

    print("wait for all server tests to finish (up to 10 min.)", flush=True)
    deadline = time.time() + 600
    for p in procs:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        p.join(remaining)
    for p in procs:
        if p.is_alive():
            print(f'terminating hung process {p.pid}', flush=True)
            p.terminate()

    simple_store(r)
    r.close()
    r.cancel_join_thread()

    print("Done testing.", flush=True)

# if len(tkids) > 0:
#     ALARM = alarms('Analytics', 'Frontier', 'Bad SQL queries')
#     ALARM.addAlarm(
#         body='Bad SQL queries',
#         source={'users': list(users), 'tkids': list(tkids)}
#     )
