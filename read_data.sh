#!/bin/bash

# get all XCaches from VP
curl -XGET https://vps.cern.ch/liveness | jq . | grep address | awk -F'"' {'print $4'} > ips.txt

echo "using $1 and $2"

# get from rucio path to the file
fp=$(rucio list-file-replicas tests:xc_test_1.dat --protocol root | grep tests | awk '{print $12}')
echo "to read $fp"

while read serv; do
    echo "testing $serv"
    # xrdcp with timeout
    timeout 30 xrdcp -f root://$serv//$fp /dev/null
done <ips.txt

