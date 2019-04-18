#!/usr/bin/env python
import sys
import os

#-c:v libx264 \

command = """ffmpeg \
-hwaccel cuvid \
-i {vidIn} \
-i {audIn} \
-map 1:a \
-map 1:a \
\
-map 0:v \
-map 0:v \
-map 0:v \
-map 0:v \
-map 0:v \
-map 0:v \
-map 0:v \
-map 0:v \
\
-c:a libfdk_aac \
-c:v libx264 \
\
-b:a:0 200k \
-b:a:1 100k \
\
-s:v:0 320x180 \
-s:v:1 320x180 \
-s:v:2 480x270 \
-s:v:3 640x360 \
-s:v:4 640x360 \
-s:v:5 768x432 \
-s:v:6 1024x576 \
-s:v:7 1280x720 \
-s:v:8 1920x1080 \
-b:v:0 200k \
-b:v:1 400k \
-b:v:2 600k \
-b:v:3 800k \
-b:v:4 1000k \
-b:v:5 1500k \
-b:v:6 2500k \
-b:v:7 4000k \
-b:v:8 8000k \
\
-r:v 30 \
-profile:v baseline \
-level:v 3.0 \
-bf 1 \
-keyint_min 120 \
-g 120 \
-sc_threshold 0 \
-b_strategy 0 \
-ar:a:1 22050 \
-use_timeline 1 \
-use_template 1 \
-adaptation_sets "id=0,streams=v id=1,streams=a" \
-f dash \
{vidOut}
"""
#print command

srcDir = sys.argv[1]
srcTmp = sys.argv[2]
dstDir = sys.argv[3]
for x in os.listdir(srcDir):
    pSrc = os.path.join(srcDir, x)
    tSrc = os.path.join(srcTmp, x)

    tDst = x+".tmp"
    dDst = os.path.join(dstDir, x)
    ttDs = os.path.join(tDst, "media")

    vIn = os.path.join(pSrc, "vid")
    aIn = os.path.join(pSrc, "aud")
    out = os.path.join(ttDs, "vid.mpd")

    os.makedirs(ttDs)

    cmd = command.format(vidIn = vIn, audIn = aIn, vidOut=out)
    print cmd
    #os.makedirs(
    os.system(cmd)
    os.rename(tDst, dDst)
    os.rename(pSrc, tSrc)

    break
