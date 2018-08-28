#!/bin/bash

DOMAIN=$1
KEY=$2

IPV4=$(curl -s https://httpbin.org/ip | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')

if [[ -n $IPV4 ]]; then 
    echo "Update IPv4: $IPV4"
    curl -s "https://dyn.dns.he.net/nic/update" \
        -d "hostname=$DOMAIN" \
        -d "password=$KEY" \
        -d "myip=$IPV4" \
        --connect-timeout 2000
    echo
fi
