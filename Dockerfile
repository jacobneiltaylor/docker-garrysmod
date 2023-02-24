FROM --platform=amd64 jacobneiltaylor/steamcmd

RUN install_depot.sh 232330 && install_depot.sh 4020
COPY ./scripts/ bin/

COPY ./files/manifest.json .

WORKDIR /opt/steam/apps/4020/garrysmod

COPY ./files/mount.cfg ./cfg
COPY ./files/server.cfg ./cfg
COPY ./files/users.cfg ./settings

RUN install_zip_package.sh https://ulyssesmod.net/archive/ULib/ulib-v2_63.zip ./addons/ulib && \
    install_zip_package.sh https://ulyssesmod.net/archive/ulx/ulx-v3_73.zip ./addons/ulx && \
    install_zip_package.sh https://fastdl.jacobtaylor.id.au/drop/ttt_ulx.zip ./addons/ulx_ttt && \
    install_zip_package.sh https://fastdl.jacobtaylor.id.au/drop/assets_ttt.zip ./ && \
    install_zip_package.sh https://fastdl.jacobtaylor.id.au/drop/assets_elevator.zip ./

EXPOSE 27005/udp
EXPOSE 27015/tcp
EXPOSE 27015/udp
EXPOSE 27020/udp

CMD [ "/opt/steam/bin/entrypoint.sh" ]
