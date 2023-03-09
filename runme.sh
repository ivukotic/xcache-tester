#!/bin/bash

voms-proxy-init --pwstdin -key /etc/grid-certs/userkey.pem \
                  -cert /etc/grid-certs/usercert.pem \
                  --voms=atlas \
                  <  /etc/grid-certs-ro/passphrase

voms-proxy-info

export X509_USER_PROXY=/tmp/x509up_u0
echo 'creating dataset'

fd=$(date +'%Y-%m-%d')
./create_dataset.sh $fd

echo 'start reading'
for i in {1..288}
do
    echo "Read attempt: $i"
    timeout 290 ./read_data.sh $fd $i
    sleep 300  
done

