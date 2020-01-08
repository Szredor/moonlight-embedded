#! /bin/bash

./moonlight-embedded-KSM/moonlight stream 10.0.10.80 -app mstsc.exe -1080 -fps 60 -bitrate 40960 #1>moonlight-tests/hl2_40M_npinning_00.out 2>moonlight-tests/hl2_40M_npinning_00.err
