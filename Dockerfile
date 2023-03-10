FROM sslhep/rucio-client:main

RUN yum install -y jq xrootd-client
RUN python3.9 -m pip install gfal2-python3

ENV X509_CERT_DIR /etc/grid-security/certificates

COPY *.sh ./

CMD [ "runme.sh" ]