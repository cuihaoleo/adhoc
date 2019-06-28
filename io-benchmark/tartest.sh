#!/bin/bash

TARGET="$1"
MINSIZE=1    # in KB
MAXSIZE=64
TOTAL=65536

cleanup() {
    rm -rf "$TARGET/tartest"
    rm -f "$TARGET/tartest.tar"
}
trap cleanup EXIT

init() {
    rm -rf "$TARGET/tartest"
    rm -f "$TARGET/tartest.tar"
    mkdir -p "$TARGET/tartest"
}

write_test() {
    local d=$((MAXSIZE-MINSIZE))
    for ((i=0; i<TOTAL; i++)); do
        local size=$(($RANDOM%d + MINSIZE))
        dd if=/dev/urandom of="$TARGET/tartest/file$i" bs=${size} count=1
    done
    sync
}

read_test() {
    tar cf "$TARGET/tartest.tar" "$TARGET/tartest"
}

rm_test() {
    rm -rf "$TARGET/tartest"
    sync
}

export PATH="/usr/local/bin/:$PATH"
init
sync
(time -p write_test) 2>&1 \
    | grep -Po 'real \K[0-9.]+' \
    | tr -d '\n'

echo -ne "\t"
sync
(time -p read_test) 2>&1 \
    | grep -Po 'real \K[0-9.]+' \
    | tr -d '\n'

echo -ne "\t"
sync
(time -p rm_test) 2>&1 \
    | grep -Po 'real \K[0-9.]+' \
    | tr -d '\n'
