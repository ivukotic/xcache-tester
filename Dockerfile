FROM sslhep/rucio-client:2025-03-update

# RUN rm -f /usr/bin/python3 && ln -s /usr/bin/python3.6 /usr/bin/python3
RUN yum update -y && yum install -y jq xrootd-client python3-gfal2 gfal2-all gfal2-util-scripts python3-gfal2-util

# for future development - python client running instead of xrdcp.  
RUN yum install -y cmake gcc gcc-c++ zlib-devel python3-devel libuuid-devel openssl-devel sudo

RUN pip install --upgrade argcomplete rucio-clients 
RUN pip install wheel 
RUN pip install xrootd 
RUN pip install elasticsearch

COPY xcache-traces.py ./
COPY xcache-tester.py ./

# COPY vomses ./
ENV X509_CERT_DIR /etc/grid-security/certificates

COPY *.sh ./

CMD [ "./runme.sh" ]