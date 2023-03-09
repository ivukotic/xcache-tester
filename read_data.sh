#!/bin/bash

# get all XCaches from VP
curl -XGET https://vps.cern.ch/liveness | jq . | grep address | awk -F'"' {'print $4'} > ips.txt

echo "using $1 and $2"
while read serv; do
    echo "$serv"
    # xrdcp with timeout
    # timeout 30 xrdcp -f root://$serv//$origin/xc/fn /dev/null
done <ips.txt

