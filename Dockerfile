FROM sslhep/rucio-client:main

RUN yum update -y && yum install -y jq xrootd-client python3-gfal2 gfal2-all gfal2-util-scripts python3-gfal2-util

RUN yum install -y cmake gcc gcc-c++ zlib-devel python3-devel libuuid-devel openssl-devel sudo

RUN pip install --upgrade argcomplete rucio-clients 
RUN pip install wheel 
RUN pip install xrootd 
RUN pip install elasticsearch

COPY xcache-traces.py ./
COPY xcache-tester.py ./

ENV X509_CERT_DIR /etc/grid-security/certificates

COPY *.sh ./

CMD [ "./runme.sh" ]