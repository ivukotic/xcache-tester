FROM sslhep/rucio-client:main

RUN ADD "https://dmc-repo.web.cern.ch/dmc-repo/dmc-el7.repo" "/etc/yum.repos.d/"

RUN yum update -y && yum install -y jq xrootd-client python3-gfal2 gfal2-all gfal2-util
RUN python3 -m pip install --upgrade rucio-clients

ENV X509_CERT_DIR /etc/grid-security/certificates

COPY *.sh ./

CMD [ "runme.sh" ]