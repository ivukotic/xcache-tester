FROM sslhep/rucio-client:main

ARG XROOTD_VERSION=6.2.1

# Upstream XRootD repo (OSG only ships 5.9.x in main). priority=1 beats the OSG repos (priority 98).
RUN printf '%s\n' \
      '[xrootd-stable]' \
      'name=XRootD Stable Repository' \
      'baseurl=https://xrootd.web.cern.ch/repo/stable/el$releasever/$basearch' \
      'gpgcheck=1' \
      'gpgkey=https://xrootd.web.cern.ch/repo/RPM-GPG-KEY.txt' \
      'enabled=1' \
      'priority=1' \
      > /etc/yum.repos.d/xrootd-stable.repo

RUN yum update -y && \
    yum install -y jq python3-pip \
        xrootd-client-${XROOTD_VERSION} python3-xrootd-${XROOTD_VERSION} && \
    yum clean all

RUN pip3 install --upgrade argcomplete rucio-clients elasticsearch

RUN python3 --version && \
    python3 -c "import XRootD; print('python xrootd', XRootD.__file__)" && \
    xrdcp --version && \
    rpm -qa | grep -i xrootd

COPY xcache-traces.py ./
COPY xcache-tester.py ./

ENV X509_CERT_DIR=/etc/grid-security/certificates

COPY *.sh ./

CMD [ "./runme.sh" ]
