#!/bin/bash

voms-proxy-init --pwstdin -key /etc/grid-certs/userkey.pem \
                  -cert /etc/grid-certs/usercert.pem \
                  --voms=%s \
                  <  /etc/grid-certs-ro/passphrase
                  
voms-proxy-info

echo 'creating dataset'
create_dataset.sh

echo 'start reading'
for i in {1..288}
do
    echo "Read attempt: $i"
    fn=$(date +'%Y-%m-%d')
    timeout 290 read_data.sh $i
    sleep 300  
done

