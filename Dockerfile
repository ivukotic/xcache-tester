FROM sslhep/rucio-client:main


COPY *.sh .

CMD [ "runme.sh" ]