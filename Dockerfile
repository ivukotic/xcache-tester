FROM sslhep/rucio-client:main

RUN yum update -y && yum install -y jq xrootd-client python3-gfal2 gfal2-all gfal2-util-scripts python3-gfal2-util

RUN yum install -y cmake gcc gcc-c++ zlib-devel python3-devel libuuid-devel openssl-devel sudo python3-pip

RUN pip3 install --upgrade argcomplete rucio-clients
RUN pip3 install wheel
RUN pip3 install xrootd==5.9.7
RUN pip3 install elasticsearch

RUN python3 --version && \
    python3 -c "import XRootD; print('python xrootd', getattr(XRootD, '__version__', 'unknown'), XRootD.__file__)" && \
    pip3 show xrootd | grep -i '^version' && \
    xrdcp --version && \
    rpm -qa | grep -i xrootd

COPY xcache-traces.py ./
COPY xcache-tester.py ./

ENV X509_CERT_DIR=/etc/grid-security/certificates

COPY *.sh ./

CMD [ "./runme.sh" ]