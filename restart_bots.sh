#!/bin/bash
# 输出 cron 执行时的环境变量
echo "当前环境变量:" >> /opt/daixin/binance/restart_bots.log
env >> /opt/daixin/binance/restart_bots.log

# 输出用户信息
echo "当前用户: $(whoami)" >> /opt/daixin/binance/restart_bots.log

# Load Conda environment
eval "$(/opt/anaconda3/bin/conda shell.bash hook)"
conda activate bot

echo "开始执行脚本: $(date)" >> /opt/daixin/binance/restart_bots.log
/usr/bin/nohup /opt/anaconda3/envs/bot/bin/python -u /opt/daixin/binance/binance_recommed.py >> push.log 2>&1 &
