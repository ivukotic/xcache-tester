#!/bin/bash
dat=$(date +'%Y-%m-%d')

# get all XCaches from VP
curl -XGET https://vps.cern.ch/liveness | jq . | grep address | awk -F'"' {'print $4'} > ips.txt

echo "using $dat and $1"

ds=user.ivukotic:user.ivukotic.xcache_$dat
# get from rucio path to the file
fp=$(rucio list-file-replicas $ds --protocol root | grep xcache_${dat}_${1}.dat | awk '{print $12}')
echo "to read $fp"

while read serv; do
    # skip local addresses.
    if [[ $serv = 10.* ]]; then 
        continue
    fi
    # skip OX non VP server.
    if [[ $serv = 163.1.5.200 ]]; then 
        continue
    fi
    echo "testing $serv"
    # xrdcp with timeout
    cmd="xrdcp -f -s root://$serv//$fp /dev/null"
    echo $cmd
    timeout 30 $cmd
    rc=$?

    if [ $rc -ne 0 ]; then
        echo "issue with server: ${serv}. ret. code: $rc"
        
        curl -s -X POST https://aaas.atlas-ml.org/alarm \
        -H 'Content-Type: application/json' \
        -d '{ "category" : "Virtual Placement", "subcategory": "XCache", "event": "external test", "body": "error code: '$rc' ", "tags":"'$serv'", "source": {"server_ip":"'$serv'"}}'
    fi

done <ips.txt

echo '====================================================='
echo 'series done.'