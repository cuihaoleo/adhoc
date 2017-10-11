#!/bin/bash

DOMAIN=$1
KEY=$2

IPV4=$(ip route get 1 | grep -Po '(?<=src )[^ ]+')
IPV6=$(ip route get 2001:: | grep -Po '(?<=src )[^ ]+')

if [[ -n $IPV4 ]]; then 
    echo "Update IPv4: $IPV4"
    curl -q "https://dyn.dns.he.net/nic/update" \
        -d "hostname=$DOMAIN" \
        -d "password=$KEY" \
        -d "myip=$IPV4" \
        --connect-timeout 2000
    echo
fi

if [[ -n $IPV6 ]]; then 
    echo "Update IPv6: $IPV6"
    curl -q "https://dyn.dns.he.net/nic/update" \
        -d "hostname=$DOMAIN" \
        -d "password=$KEY" \
        -d "myip=$IPV6" \
        --connect-timeout 2000
fi
