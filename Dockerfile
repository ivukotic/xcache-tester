FROM sslhep/rucio-client:main

RUN yum install -y jq

ENV X509_CERT_DIR /etc/grid-security/certificates

COPY *.sh ./

CMD [ "runme.sh" ]