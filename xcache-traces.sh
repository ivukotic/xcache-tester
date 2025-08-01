#!/bin/bash
date

voms-proxy-init3 --pwstdin -voms atlas \
                -key /etc/grid-certs/userkey.pem \
                -cert /etc/grid-certs/usercert.pem \
                -valid "24:00" \
                <  /etc/grid-certs-ro/passphrase

voms-proxy-info3

export X509_USER_PROXY=/tmp/x509up_u0

python3.6 xcache-traces.py
rc=$?; if [[ $rc != 0 ]]; then 
    echo "problem checking rucio traces. Exiting."
    exit $rc
fi
