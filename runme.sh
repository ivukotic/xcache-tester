#!/bin/bash

voms-proxy-init3 --pwstdin -key /etc/grid-certs/userkey.pem \
                  -cert /etc/grid-certs/usercert.pem \
                  -voms atlas \
                #   -vomses vomses \
                  -valid "25:00" \
                  <  /etc/grid-certs-ro/passphrase

voms-proxy-info3

export X509_USER_PROXY=/tmp/x509up_u0

echo 'start reading'

export PYTHONUNBUFFERED=TRUE
python3 xcache-tester.py

