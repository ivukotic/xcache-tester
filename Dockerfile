FROM sslhep/rucio-client


COPY *.sh .

CMD [ "runme.sh" ]