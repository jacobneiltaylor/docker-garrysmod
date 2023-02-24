#!/bin/bash
set -eux

install_depot.sh 232330
install_depot.sh 4020

cd ~

/opt/steam/apps/4020/srcds_run "@"
