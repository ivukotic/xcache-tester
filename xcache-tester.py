# every 5 min tries to access one of the test files through each xcache server sending heartbeats

# status:
# xcache_open => xopen_
# xcahe_read => xread_
# cache fevict before the test => expunge_ok, expunge_message
# origin (written only when the origin check fails) => origin_ok, origin_version, ostat_, oopen_, oread_

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
from XRootD.client.flags import QueryCode

import faulthandler
import signal
faulthandler.register(signal.SIGUSR1.value)

nproc = 5
procs = []  # (doc, Process)


def addStatus(doc, step, status):
    doc[step+'ok'] = status.ok
    doc[step+'error'] = status.error
    doc[step+'fatal'] = status.fatal
    doc[step+'message'] = status.message
    doc[step+'status'] = status.status
    doc[step+'code'] = status.code


def expunge(doc, tag):
    # Fills doc with expunge_ok/expunge_message.
    nfp = '/atlas/rucio/user/ivukotic/7d/9b/xcache.test.dat'
    try:
        cp = subprocess.run(
            ["xrdfs", doc['server'], "cache", "fevict", nfp],
            capture_output=True, text=True, timeout=30)
        doc['expunge_ok'] = cp.returncode == 0
        if cp.returncode:
            doc['expunge_message'] = (cp.stderr or cp.stdout).strip()
    except subprocess.TimeoutExpired:
        doc['expunge_ok'] = False
        doc['expunge_message'] = 'timed out after 30s'
    if doc['expunge_ok']:
        print(f'{tag} expunge: OK', flush=True)
    else:
        print(f'{tag} expunge: FAILED {doc["expunge_message"]}', flush=True)


def test_server(doc, r):
    # Runs in its own subprocess so all XRootD TCP connections are closed on exit,
    # signalling xcache to close its origin connections.
    c = 'root://' + doc['server']
    op = doc['fp']
    o = op[:op.index('//', 10)]
    p = op[op.index('//', 10):]
    tag = f"[{doc['site']} {doc['server']}]"

    expunge(doc, tag)

    try:
        with client.File() as f:
            print(f'{tag} checking {c}//{op}', flush=True)
            xostatus, nothing = f.open(c+'//'+o+p, timeout=5)
            print(f'{tag} xopen: {xostatus}', flush=True)
            addStatus(doc, 'xopen_', xostatus)
            if xostatus.ok:
                xrstatus, data = f.read(offset=0, size=1024, timeout=10)
                print(f'{tag} xread: {xrstatus}', flush=True)
                addStatus(doc, 'xread_', xrstatus)
    except Exception as e:
        print(f'{tag} issue reading file from xcache.', e, flush=True)

    r.put(doc)


def checkOrigin(doc):
    # Fills doc with ostat_/oopen_/oread_ statuses and origin_ok; returns origin_ok.
    fp = doc['fp']
    o = fp[:fp.index('//', 10)]
    p = fp[fp.index('//', 10):]
    doc['origin_ok'] = False
    print("---", datetime.datetime.now(), "---")
    myclient = client.FileSystem(o)

    # best effort: needs a successful login, so it fails the same way as stat on auth problems
    try:
        vstatus, version = myclient.query(QueryCode.CONFIG, 'version', timeout=5)
        if vstatus.ok:
            doc['origin_version'] = version.decode(errors='replace').strip()
            print(f'origin version: {doc["origin_version"]}', flush=True)
        else:
            print(f'origin version query failed: {vstatus}', flush=True)
    except Exception as e:
        print('issue querying origin version.', e, flush=True)

    print("stating origin", flush=True)

    try:
        status, statInfo = myclient.stat(p, timeout=5)
        print(f'origin stat:{status}', flush=True)  # , statInfo)
        addStatus(doc, 'ostat_', status)
    except Exception as e:
        print('issue stating file.', e, flush=True)
        doc['origin_message'] = f'stat exception: {e}'
        return False

    if not status.ok:
        return False

    print("opening and reading from origin", flush=True)

    try:
        with client.File() as f:
            print("opening:", fp, flush=True)
            ostatus, nothing = f.open(fp, timeout=5)
            print(f'open: {ostatus}', flush=True)
            addStatus(doc, 'oopen_', ostatus)
            if ostatus.ok:
                rstatus, data = f.read(offset=0, size=1024, timeout=10)
                print(f'read: {rstatus}', flush=True)
                addStatus(doc, 'oread_', rstatus)
    except Exception as e:
        print('issue reading file from origin.', e, flush=True)
        doc['origin_message'] = f'open/read exception: {e}'
        return False

    if not ostatus.ok or not rstatus.ok:
        return False

    doc['origin_ok'] = True
    return True


def simple_store(docs):
    print("storing results.", flush=True)
    allDocs = []
    for doc in docs:
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
        print(e, flush=True)
        for err in e.errors:
            print(err, flush=True)
    except Exception as e:
        print('Something seriously wrong happened.', e, flush=True)
    print('done storing.', flush=True)


def print_summary(docs):
    def step(doc, name):
        if name + 'ok' not in doc:
            return '-'
        return 'OK' if doc[name + 'ok'] else 'FAIL'

    print(f'{"site":<20} {"server":<40} {"expunge":<8} {"open":<5} {"read":<5} message', flush=True)
    for doc in sorted(docs, key=lambda d: (d['site'], d['server'])):
        message = ''
        for name in ('xread_', 'xopen_'):
            if doc.get(name + 'ok') is False:
                message = doc.get(name + 'message', '')
        print(f'{doc["site"]:<20} {doc["server"]:<40} {step(doc, "expunge_"):<8} '
              f'{step(doc, "xopen_"):<5} {step(doc, "xread_"):<5} {message.strip()}', flush=True)
    ok = sum(1 for d in docs if d.get('xread_ok'))
    print(f'servers OK: {ok}/{len(docs)}', flush=True)


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
        basic_auth=(config['ES_USER'], config['ES_PASS'])).options(request_timeout=60)

    if es.ping():
        print('connected to ES.')
    else:
        print('no connection to ES.')
        sys.exit(1)

    r = Queue()  # a queue for results

    # Origins holding the test file, in order of preference. The first one that
    # passes checkOrigin is used for all xcache tests.
    origins = [
        'root://xrootd.aglt2.org:1094//atlaslocalgroupdisk/rucio/user/ivukotic/7d/9b/xcache.test.dat',
        'root://xrootd.data.net2.mghpcc.org:1094//atlaslocalgroupdisk/rucio/user/ivukotic/7d/9b/xcache.test.dat',
        'root://dcgftp.usatlas.bnl.gov:1094//pnfs/usatlas.bnl.gov/LOCALGROUPDISK/rucio/user/ivukotic/7d/9b/xcache.test.dat',
        'root://fax.mwt2.org:1094//pnfs/uchicago.edu/atlaslocalgroupdisk/rucio/user/ivukotic/7d/9b/xcache.test.dat',
    ]
    cd = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    print('starting at:', cd)

    servers = get_active_xcaches()

    fp = None
    failed_origins = []
    for candidate in origins:
        origin_doc = {'fp': candidate}
        if checkOrigin(origin_doc):
            fp = candidate
            break
        print(f'origin failed, trying next one: {candidate}', flush=True)
        failed_origins.append(origin_doc)

    # record origin failures so they are visible in ES, not just in pod logs
    if failed_origins:
        simple_store(failed_origins)

    if fp is None:
        print('Test file issue on all origins. Quitting after an hour of sleep')
        time.sleep(3600)
        sys.exit(1)
    print('using origin:', fp, flush=True)

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
        procs.append((doc, p))

        # Throttle: keep at most nproc tests running concurrently
        while sum(1 for _, proc in procs if proc.is_alive()) >= nproc:
            time.sleep(1)

    print("wait for all server tests to finish (up to 10 min.)", flush=True)
    deadline = time.time() + 600
    for _, p in procs:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        p.join(remaining)
    hung = set()
    for doc, p in procs:
        if p.is_alive():
            print(f'terminating hung process {p.pid} ({doc["server"]})', flush=True)
            hung.add(id(doc))
            p.terminate()
            p.join(5)

    docs = []
    while not r.empty():
        docs.append(r.get())

    # Servers whose test never reported (hung and killed, or crashed) are failures too.
    reported = {(d['server_id'], d['server']) for d in docs}
    for doc, p in procs:
        if (doc['server_id'], doc['server']) in reported:
            continue
        if id(doc) in hung:
            msg = 'test did not finish within 600s; process terminated'
        else:
            msg = f'test process exited without reporting (exitcode {p.exitcode})'
        print(f'{doc["server"]}: {msg}', flush=True)
        doc['xopen_ok'] = False
        doc['xopen_error'] = True
        doc['xopen_message'] = msg
        docs.append(doc)

    print_summary(docs)
    simple_store(docs)
    r.close()
    r.cancel_join_thread()

    print("Done testing.", flush=True)

# if len(tkids) > 0:
#     ALARM = alarms('Analytics', 'Frontier', 'Bad SQL queries')
#     ALARM.addAlarm(
#         body='Bad SQL queries',
#         source={'users': list(users), 'tkids': list(tkids)}
#     )
