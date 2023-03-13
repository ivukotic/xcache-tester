#!/bin/bash
dat=$1
# get all XCaches from VP
curl -XGET https://vps.cern.ch/liveness | jq . | grep address | awk -F'"' {'print $4'} > ips.txt

echo "using $dat and $2"

ds=user.ivukotic:user.ivukotic.xcache_$dat
# get from rucio path to the file
fp=$(rucio list-file-replicas $ds --protocol root | grep xcache_$dat_$2.dat | awk '{print $12}')
echo "to read $fp"

while read serv; do
    echo "testing $serv"
    # xrdcp with timeout
    timeout 30 xrdcp -f root://$serv//$fp /dev/null
done <ips.txt

