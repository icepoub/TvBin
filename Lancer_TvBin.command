#!/bin/bash
cd "$(dirname "$0")"
lsof -ti:8070 | xargs kill -9 2>/dev/null
sleep 1
/Users/icepoub/Downloads/DevHARD/TvBin/venv/bin/python3 run_on_8070.py 
exit