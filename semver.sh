#!/bin/bash

V0=$(git describe --long --exclude=nightly | sed -n 's/v\?\([0-9\.]*\)-\([0-9]*\)-.*/\1.\2/p')
IFS='.' read -d "" -ra arr0 <<< $V0
((arr0[2]=${arr0[2]} + ${arr0[3]}))
V=${arr0[0]}.${arr0[1]}.${arr0[2]}
echo "__version__ = '$V'" > GeoscanDecoder/version.py
echo $V
