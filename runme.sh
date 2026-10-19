#!/bin/bash

echo '--- versions ---'
python3 --version
python3 -c "import XRootD; print('python xrootd', getattr(XRootD, '__version__', 'unknown'), XRootD.__file__)"
pip3 show xrootd | grep -i '^version'
xrdcp --version
rpm -qa | grep -i xrootd
echo '----------------'

voms-proxy-init3 --pwstdin -key /etc/grid-certs/userkey.pem \
                  -cert /etc/grid-certs/usercert.pem \
                  -voms atlas \
                  -valid "25:00" \
                  <  /etc/grid-certs-ro/passphrase

                #   -vomses vomses \
                
voms-proxy-info3

export X509_USER_PROXY=/tmp/x509up_u0

echo 'start reading'

export PYTHONUNBUFFERED=TRUE
python3 xcache-tester.py

