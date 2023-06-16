# looks up Rucio traces from UC ES,
# filters bad transfers through xcaches
# retries and classifies them
# ====
# TODO
# make it create Alarms.

#  stateReason: direct_access can result in clientState: FOUND_ROOT or FAILED_REMOTE_OPEN
#  stateReason: OK can result in clientState: DONE, SERVICE_ERROR, CP_TIMEOUT, COPY_ERROR

# retry status:
# origin stat => nothing
# origin open => open_
# origin read => read_
# xcache_open => xopen_
# xcahe_read => xread_

import sys
import datetime
import time
# from alerts import alarms
from elasticsearch import Elasticsearch, helpers, exceptions as es_exceptions
# from elasticsearch.helpers import scan
import json

from multiprocessing import Process, Queue

from XRootD import client

nhours = 24
nproc = 5
procs = []
results = 0


def splitURL(url):
    originStart = url.index('root:', 5)
    cache = url[:originStart-2]
    op = url[originStart:]

    pathStart = op.index('1094/', 8)+4
    origin = op[:pathStart]
    opath = op[pathStart:]
    return cache, origin, opath


def addStatus(doc, step, status):
    doc[step+'ok'] = status.ok
    doc[step+'error'] = status.error
    doc[step+'fatal'] = status.fatal
    doc[step+'message'] = status.message
    doc[step+'status'] = status.status
    doc[step+'code'] = status.code


def stater(i, q, r):
    while not q.empty():
        doc = q.get()
        if doc is None:
            q.put(None)
            break
        fileID = doc['fileID']
        c, o, p = splitURL(doc['url'])
        print(f'thr:{i}, <{fileID}>, checking cache {c} origin {o} for {p}')
        myclient = client.FileSystem(o)
        try:
            myclient = client.FileSystem(o)
            status, statInfo = myclient.stat(p, timeout=5)
            print(f'<{fileID}> stat:{status}')  # , statInfo)
            addStatus(doc, '', status)
            doc['_index'] = "remote_io_retries"
            doc['xcache'] = c
            doc['origin'] = o
            doc['timestamp'] = int(time.time()*1000)
        except Exception as e:
            print('issue stating file.', e)

        if not status.ok:
            r.put(doc, block=True, timeout=0.1)
            continue

        try:
            with client.File() as f:
                # print("opening:", o+p)
                ostatus, nothing = f.open(o+p, timeout=5)
                print(f'<{fileID}> open: {ostatus}')
                addStatus(doc, 'open_', ostatus)
                if ostatus.ok:
                    rstatus, data = f.read(offset=0, size=1024, timeout=10)
                    print(f'<{fileID}> read: {rstatus}')
                    addStatus(doc, 'read_', rstatus)
        except Exception as e:
            print('issue reading file from origin.', e)

        if 'read_ok' not in doc or not doc['read_ok']:
            r.put(doc, block=True, timeout=0.1)
            continue

        try:
            with client.File() as f:
                # print("opening through xcache:", c+'//'+o+p)
                xostatus, nothing = f.open(c+'//'+o+p, timeout=5)
                print(f'<{fileID}> xopen: {xostatus}')
                addStatus(doc, 'xopen_', xostatus)
                if xostatus.ok:
                    xrstatus, data = f.read(offset=0, size=1024, timeout=10)
                    print(f'<{fileID}>xread: {xrstatus}')
                    addStatus(doc, 'xread_', xrstatus)
        except Exception as e:
            print('issue reading file from xcache.', e)

        r.put(doc, block=True, timeout=0.1)

    print(f'thr:{i} done.')


def simple_store(r):
    print("storring results.")
    allDocs = []
    while not r.empty():
        doc = r.get()
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

    ct = datetime.datetime.utcnow()
    curtime = ct.strftime('%Y%m%dT%H%M%S.%f')[:-3] + 'Z'

    td = datetime.timedelta(hours=nhours)
    st = ct - td
    starttime = st.strftime('%Y%m%dT%H%M%S.%f')[:-3] + 'Z'

    print('start time', starttime)
    print('current time', curtime)

    my_query = {
        "bool": {
            "must": [
                {
                    "wildcard": {"url": {"value": "root*//root*"}}
                },
                {
                    "range": {
                        "@timestamp": {
                            "gte": starttime,
                            "lte": curtime,
                            "format": "basic_date_time"
                        }
                    }
                }
            ],
            "must_not": [
                {
                    "term": {"clientState": "FOUND_ROOT"}
                },
                {
                    "term": {"clientState": "DONE"}
                },
            ]
        }
    }

    res = es.search(index='rucio_traces', query=my_query, size=10000)
    results = res['hits']['total']['value']
    print('total results:', results)

    keep = [
        'clientState', 'stateReason', 'scope', 'filename', 'eventType', 'localSite',
        'dataset', 'filesize', 'timeStart', 'hostname', 'taskid', 'appid', 'url', 'remoteSite', 'pq'
    ]

    q = Queue()  # a queue for files to retry
    r = Queue()  # a queue for results

    # reads the docs selected, adds them to queue 'q'
    fileID = 0
    for i in range(results):
        doc = res['hits']['hits'][i]['_source']
        ndoc = {k: doc[k] for k in keep}
        # print(ndoc)
        if 'root://localhost' in ndoc['url']:
            continue
        ndoc['fileID'] = fileID
        fileID += 1
        q.put(ndoc)

    q.put(None)

    # creates processes that will do retries
    for i in range(nproc):
        p = Process(target=stater, args=(i, q, r))
        p.start()
        procs.append(p)

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
