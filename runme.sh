#!/bin/bash

voms-proxy-init --pwstdin -key /etc/grid-certs/userkey.pem \
                  -cert /etc/grid-certs/usercert.pem \
                  --voms=atlas \
                  -valid "24:00" \
                  <  /etc/grid-certs-ro/passphrase

voms-proxy-info

export X509_USER_PROXY=/tmp/x509up_u0
echo 'creating dataset'

fd=$(date +'%Y-%m-%d')
./create_dataset.sh

echo 'start reading'
python3.6 xcache-tester.py

# for i in {1..288}
# do
#     echo "Read attempt: $i"
#     timeout 290 ./read_data.sh $i
#     sleep 300  
# done

