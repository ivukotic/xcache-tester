FROM sslhep/rucio-client:main

RUN rm -f /usr/bin/python3 && ln -s /usr/bin/python3.6 /usr/bin/python3
RUN yum update -y && yum install -y jq xrootd-client python3-gfal2 gfal2-all gfal2-util
RUN python3 -m pip install --upgrade argcomplete rucio-clients

ENV X509_CERT_DIR /etc/grid-security/certificates

COPY *.sh ./

CMD [ "runme.sh" ]